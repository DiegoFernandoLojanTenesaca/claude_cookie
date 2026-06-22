#!/usr/bin/env python3
"""Extrae los cookies de claude.ai del navegador y los respalda en
Google Drive (rclone) y/o en un Google Sheet. Multiplataforma:
Linux / Windows / macOS (browser_cookie3 descifra en los tres).

Config en ~/.config/claude-cookie-backup/config.json (o %APPDATA% en Windows):
  drive_folder   carpeta local donde dejar el .json
  rclone_remote  remoto rclone (ej "gdrive:"); cada PC sube a su subcarpeta
  sheet_webhook  URL del Apps Script (opcional)
  keep           cuantos backups conservar (default 3)
  browser        navegador forzado ("chrome"/"firefox"/...); "" = auto
Las variables de entorno con el mismo nombre en MAYUSCULA tienen prioridad.

Regla anti-basura: si no aparece sessionKey, aborta sin sobrescribir.
"""
import os, sys, json, glob, shutil, socket, datetime, subprocess, urllib.request

DOMAIN = "claude.ai"
BROWSERS = ["chrome", "brave", "chromium", "edge", "opera", "vivaldi", "firefox"]


def config_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "claude-cookie-backup")


def load_config():
    cfg = {"drive_folder": "", "rclone_remote": "", "sheet_webhook": "",
           "keep": 3, "days": 15, "browser": ""}
    try:
        with open(os.path.join(config_dir(), "config.json")) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    # overrides por entorno (compat con el service viejo de systemd)
    for k, env in (("drive_folder", "DRIVE_FOLDER"), ("rclone_remote", "RCLONE_REMOTE"),
                   ("sheet_webhook", "SHEET_WEBHOOK"), ("browser", "BROWSER")):
        if os.environ.get(env) is not None:
            cfg[k] = os.environ[env]
    if os.environ.get("KEEP"):
        cfg["keep"] = os.environ["KEEP"]
    cfg["keep"] = max(1, int(cfg["keep"]))
    for k in ("drive_folder", "rclone_remote", "sheet_webhook", "browser"):
        cfg[k] = (cfg[k] or "").strip()
    return cfg


def to_seconds(e):
    """expires -> segundos. Chrome los da en s (10 dig), Firefox en ms (13):
    >1e11 = ms => /1000."""
    if not e:
        return None
    e = float(e)
    return e / 1000.0 if e > 1e11 else e


def to_dict(c):
    """http.cookiejar.Cookie -> dict formato EditThisCookie."""
    exp = to_seconds(c.expires)
    d = {
        "domain": c.domain,
        "name": c.name,
        "value": c.value,
        "path": c.path or "/",
        "secure": bool(c.secure),
        "httpOnly": bool(c.has_nonstandard_attr("HttpOnly")
                         or c.has_nonstandard_attr("HTTPOnly")),
        "hostOnly": not (c.domain or "").startswith("."),
        "session": exp is None,
        "sameSite": c.get_nonstandard_attr("SameSite") or "lax",
        "storeId": "0",
    }
    if exp is not None:
        d["expirationDate"] = exp
    return d


def collect(browser=""):
    """Elige UN navegador (el del sessionKey mas fresco) y exporta solo ese,
    asi unidades y sesion quedan consistentes. `browser` fuerza uno.
    Devuelve (cookies, sessionKey, navegador)."""
    import browser_cookie3
    names = [browser] if browser else BROWSERS
    best, errs = None, []
    for name in names:
        fn = getattr(browser_cookie3, name, None)
        if not fn:
            continue
        try:
            cj = fn(domain_name=DOMAIN)
        except Exception as e:
            errs.append(f"{name}: {type(e).__name__}")
            continue
        cookies = [to_dict(c) for c in cj if DOMAIN in (c.domain or "")]
        sk = next((x for x in cookies if x["name"] == "sessionKey"), None)
        if not sk:
            continue
        score = sk.get("expirationDate", 0) or 0
        if best is None or score > best[0]:
            best = (score, name, cookies)
    if best is None:
        if errs:
            print("Sin sesion/error: " + ", ".join(errs), file=sys.stderr)
        return [], None, None
    _, name, cookies = best
    sk = next((x["value"] for x in cookies if x["name"] == "sessionKey"), None)
    return cookies, sk, name


def prune(folder, keep):
    """Deja los `keep` mas nuevos (nombre con fecha+hora => orden lexicografico
    == cronologico). Devuelve los que quedan."""
    files = sorted(glob.glob(os.path.join(folder, "claude-cookies-*.json")))
    for old in files[:-keep]:
        os.remove(old)
    return files[-keep:]


def write_file(folder, keep, payload_json, stamp):
    if not folder:
        return
    os.makedirs(folder, exist_ok=True)
    path = os.path.join(folder, f"claude-cookies-{stamp}.json")
    with open(path, "w") as f:
        f.write(payload_json)
    kept = prune(folder, keep)
    print(f"Archivo: {path}  (conservados {len(kept)})")


def find_rclone():
    for c in (shutil.which("rclone"), shutil.which("rclone.exe"),
              os.path.expanduser("~/.local/bin/rclone"),
              os.path.expanduser("~/.local/bin/rclone.exe")):
        if c and os.path.exists(c):
            return c
    return None


def push_drive(folder, remote):
    """rclone sync a la subcarpeta de ESTA PC -> varias PCs no se pisan."""
    if not (remote and folder):
        return
    rclone = find_rclone()
    if not rclone:
        print("rclone no instalado; salto subida a Drive", file=sys.stderr)
        return
    base = remote if remote.endswith((":", "/")) else remote + "/"
    target = base + socket.gethostname()
    try:
        subprocess.run([rclone, "sync", folder, target],
                       check=True, capture_output=True, timeout=300)
        print(f"Drive: sync -> {target}")
    except Exception as e:
        print(f"Drive sync fallo (sigue el archivo local): {e}", file=sys.stderr)


def push_sheet(webhook, stamp, sk, payload_json):
    if not webhook:
        return
    body = json.dumps({"fecha": stamp, "sessionKey": sk, "json": payload_json}).encode()
    req = urllib.request.Request(webhook, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
        print("Sheet: fila agregada")
    except Exception as e:
        print(f"Sheet fallo (sigue el archivo local): {e}", file=sys.stderr)


def newest_age_days(folder):
    """Edad en dias del backup mas nuevo, o None si no hay."""
    files = sorted(glob.glob(os.path.join(folder, "claude-cookies-*.json")))
    if not files:
        return None
    return (datetime.datetime.now().timestamp() - os.path.getmtime(files[-1])) / 86400.0


def main(scheduled=False):
    cfg = load_config()
    if scheduled and cfg["drive_folder"]:
        age = newest_age_days(cfg["drive_folder"])
        if age is not None and age < cfg["days"]:
            print(f"Backup reciente ({age:.1f}d < {cfg['days']}d); salto.")
            return
    cookies, sk, browser = collect(cfg["browser"])
    if not sk:
        sys.exit("X No encontre sessionKey (sesion cerrada?). No sobrescribo nada.")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    payload_json = json.dumps(cookies, indent=2, sort_keys=True)
    write_file(cfg["drive_folder"], cfg["keep"], payload_json, stamp)
    push_drive(cfg["drive_folder"], cfg["rclone_remote"])
    push_sheet(cfg["sheet_webhook"], stamp, sk, payload_json)
    print(f"OK: {len(cookies)} cookies de {browser}, sessionKey presente ({stamp})")


def _self_test():
    import tempfile
    assert to_seconds(1779124493172) == 1779124493.172   # ms -> s
    assert to_seconds(1784560472) == 1784560472          # ya en s
    assert to_seconds(None) is None and to_seconds(0) is None
    with tempfile.TemporaryDirectory() as d:
        for t in ("01", "02", "03", "04", "05"):
            open(os.path.join(d, f"claude-cookies-2026-06-22_00-00-{t}.json"), "w").close()
        kept = sorted(os.path.basename(p) for p in prune(d, 3))
        assert kept == [
            "claude-cookies-2026-06-22_00-00-03.json",
            "claude-cookies-2026-06-22_00-00-04.json",
            "claude-cookies-2026-06-22_00-00-05.json",
        ], kept
        assert len(os.listdir(d)) == 3
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "claude-cookies-2026-06-22_00-00-01.json"), "w").close()
        assert len(prune(d, 3)) == 1
    # config: env overridea al archivo
    os.environ["KEEP"] = "7"; os.environ["BROWSER"] = "firefox"
    c = load_config()
    assert c["keep"] == 7 and c["browser"] == "firefox"
    del os.environ["KEEP"], os.environ["BROWSER"]
    print("self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        main(scheduled="--scheduled" in sys.argv)
