#!/usr/bin/env python3
"""Extrae los cookies de claude.ai de todos los navegadores instalados,
los guarda como JSON (formato EditThisCookie) en una carpeta de Drive y/o
los manda a un Google Sheet via Apps Script.

Regla anti-basura: si no aparece sessionKey (sesion cerrada / lectura
fallida), aborta SIN sobrescribir ni mandar nada.

Config por variables de entorno (las pone install.sh en el service):
  DRIVE_FOLDER   carpeta sincronizada de Drive donde dejar el .json (opcional)
  SHEET_WEBHOOK  URL del Apps Script para agregar fila al Sheet (opcional)
  KEEP           cuantos backups conservar (default 3)
"""
import os, sys, json, glob, shutil, socket, datetime, subprocess, urllib.request

DOMAIN = "claude.ai"
KEEP = max(1, int(os.environ.get("KEEP", "3")))
FOLDER = os.environ.get("DRIVE_FOLDER", "").strip()
WEBHOOK = os.environ.get("SHEET_WEBHOOK", "").strip()
RCLONE_REMOTE = os.environ.get("RCLONE_REMOTE", "").strip()  # ej: gdrive:claude-cookies

BROWSERS = ["chrome", "brave", "chromium", "edge", "opera", "vivaldi", "firefox"]


def to_seconds(e):
    """Normaliza expires a segundos. Chrome los da en segundos (10 dig),
    Firefox en milisegundos (13 dig): >1e11 = ms => /1000."""
    if not e:
        return None
    e = float(e)
    return e / 1000.0 if e > 1e11 else e


def to_dict(c):
    """http.cookiejar.Cookie -> dict formato EditThisCookie. Omite
    expirationDate en cookies de sesion (como hace EditThisCookie)."""
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


def collect():
    """Elige UN navegador (no mezcla): el que tenga sessionKey con la
    expiracion mas tardia (login mas fresco) y exporta SOLO ese, asi las
    unidades y la sesion quedan consistentes. Devuelve (cookies, sk, navegador)."""
    import browser_cookie3
    best, errs = None, []
    for name in BROWSERS:
        fn = getattr(browser_cookie3, name, None)
        if not fn:
            continue
        try:
            cj = fn(domain_name=DOMAIN)
        except Exception as e:           # navegador no instalado / sin sesion
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
            print("Navegadores sin sesion/error: " + ", ".join(errs), file=sys.stderr)
        return [], None, None
    _, name, cookies = best
    sk = next((x["value"] for x in cookies if x["name"] == "sessionKey"), None)
    return cookies, sk, name


def prune(folder, keep):
    """Borra los backups viejos dejando los `keep` mas nuevos (nombre con
    fecha ISO => orden lexicografico == cronologico). Devuelve los que quedan."""
    files = sorted(glob.glob(os.path.join(folder, "claude-cookies-*.json")))
    for old in files[:-keep]:
        os.remove(old)
    return files[-keep:]


def write_file(payload_json, stamp):
    if not FOLDER:
        return
    os.makedirs(FOLDER, exist_ok=True)
    path = os.path.join(FOLDER, f"claude-cookies-{stamp}.json")
    with open(path, "w") as f:
        f.write(payload_json)
    kept = prune(FOLDER, KEEP)
    print(f"Archivo: {path}  (conservados {len(kept)})")


def remote_target():
    """Subcarpeta por PC dentro del remoto, para que varias PCs no se pisen
    al espejar: gdrive: -> gdrive:nombre-de-esta-pc."""
    base = RCLONE_REMOTE
    if not base.endswith((":", "/")):
        base += "/"
    return base + socket.gethostname()


def push_drive():
    """Sube la carpeta a Google Drive con rclone. `sync` espeja, pero cada PC
    a SU subcarpeta -> rotacion por PC sin borrar lo de las demas."""
    if not (RCLONE_REMOTE and FOLDER):
        return
    rclone = shutil.which("rclone") or os.path.expanduser("~/.local/bin/rclone")
    if not os.path.exists(rclone):
        print("rclone no instalado; salto subida a Drive", file=sys.stderr)
        return
    target = remote_target()
    try:
        subprocess.run([rclone, "sync", FOLDER, target],
                       check=True, capture_output=True, timeout=300)
        print(f"Drive: sync -> {target}")
    except Exception as e:
        print(f"Drive sync fallo (sigue el archivo local): {e}", file=sys.stderr)


def push_sheet(stamp, sk, payload_json):
    if not WEBHOOK:
        return
    body = json.dumps({"fecha": stamp, "sessionKey": sk, "json": payload_json}).encode()
    req = urllib.request.Request(WEBHOOK, data=body,
                                 headers={"Content-Type": "application/json"})
    try:
        urllib.request.urlopen(req, timeout=30).read()
        print("Sheet: fila agregada")
    except Exception as e:               # el archivo local ya quedo igual
        print(f"Sheet fallo (sigue el archivo local): {e}", file=sys.stderr)


def main():
    cookies, sk, browser = collect()
    if not sk:
        sys.exit("X No encontre sessionKey (sesion cerrada en el navegador?). "
                 "No sobrescribo nada.")
    stamp = datetime.datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    # sort_keys => mismo orden de campos que EditThisCookie (alfabetico)
    payload_json = json.dumps(cookies, indent=2, sort_keys=True)
    write_file(payload_json, stamp)
    push_drive()
    push_sheet(stamp, sk, payload_json)
    print(f"OK: {len(cookies)} cookies de {browser}, sessionKey presente ({stamp})")


def _self_test():
    import tempfile
    # normalizacion de unidades: ms (Firefox) -> s, s (Chrome) intacto
    assert to_seconds(1779124493172) == 1779124493.172   # ms -> s
    assert to_seconds(1784560472) == 1784560472          # ya en s
    assert to_seconds(None) is None and to_seconds(0) is None
    # prune: crear 5, conservar 3 => quedan los 3 ultimos por fecha
    with tempfile.TemporaryDirectory() as d:
        for day in ("01", "02", "03", "04", "05"):
            open(os.path.join(d, f"claude-cookies-2026-06-{day}.json"), "w").close()
        kept = prune(d, 3)
        assert [os.path.basename(p) for p in kept] == [
            "claude-cookies-2026-06-03.json",
            "claude-cookies-2026-06-04.json",
            "claude-cookies-2026-06-05.json",
        ], kept
        assert len(os.listdir(d)) == 3
    # prune con menos archivos que keep: no borra nada
    with tempfile.TemporaryDirectory() as d:
        open(os.path.join(d, "claude-cookies-2026-06-01.json"), "w").close()
        assert len(prune(d, 3)) == 1
    print("self-test ok")


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        _self_test()
    else:
        main()
