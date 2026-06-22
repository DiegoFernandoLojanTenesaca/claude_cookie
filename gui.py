#!/usr/bin/env python3
"""Interfaz multiplataforma para claude-cookie-backup (Tkinter/ttk, sin deps).
Extraer a demanda, copiar el cookie, elegir navegador e intervalo, abrir carpeta.
Funciona en Linux / Windows / macOS."""
import os, sys, glob, json, platform, subprocess
import tkinter as tk
from tkinter import ttk, messagebox

DIR = os.path.dirname(os.path.abspath(__file__))
PY = sys.executable
BROWSERS = ["auto", "chrome", "brave", "chromium", "edge", "opera", "vivaldi", "firefox"]
DAYS = ["10", "15", "20", "30"]
KEEPS = ["3", "5", "7", "10"]


def config_dir():
    if os.name == "nt":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
    else:
        base = os.environ.get("XDG_CONFIG_HOME") or os.path.expanduser("~/.config")
    return os.path.join(base, "claude-cookie-backup")


CFG_PATH = os.path.join(config_dir(), "config.json")


def load_cfg():
    cfg = {"drive_folder": os.path.join(DIR, "out"), "rclone_remote": "",
           "sheet_webhook": "", "keep": 3, "days": 15, "browser": ""}
    try:
        with open(CFG_PATH) as f:
            cfg.update(json.load(f))
    except (OSError, ValueError):
        pass
    return cfg


def save_cfg(cfg):
    os.makedirs(config_dir(), exist_ok=True)
    with open(CFG_PATH, "w") as f:
        json.dump(cfg, f, indent=2)


def out_folder(cfg):
    return cfg.get("drive_folder") or os.path.join(DIR, "out")


def latest(cfg):
    files = sorted(glob.glob(os.path.join(out_folder(cfg), "claude-cookies-*.json")))
    if not files:
        return None, None
    try:
        return files[-1], json.load(open(files[-1]))
    except (OSError, ValueError):
        return files[-1], None


def session_key(cookies):
    return next((c["value"] for c in (cookies or []) if c["name"] == "sessionKey"), None)


def open_path(p):
    os.makedirs(p, exist_ok=True)
    if platform.system() == "Windows":
        os.startfile(p)                      # noqa: B606
    elif platform.system() == "Darwin":
        subprocess.Popen(["open", p])
    else:
        subprocess.Popen(["xdg-open", p])


class App:
    def __init__(self, root):
        self.root = root
        self.cfg = load_cfg()
        root.title("Claude · Cookie Backup")
        root.resizable(False, False)
        frm = ttk.Frame(root, padding=16)
        frm.grid(sticky="nwes")

        ttk.Label(frm, text="Claude · Cookie Backup",
                  font=("", 15, "bold")).grid(row=0, column=0, columnspan=2, sticky="w")
        self.status = ttk.Label(frm, justify="left", foreground="#444")
        self.status.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 12))

        ttk.Button(frm, text="⟳  Extraer ahora", command=self.extract
                   ).grid(row=2, column=0, columnspan=2, sticky="we", ipady=6)

        cp = ttk.Frame(frm); cp.grid(row=3, column=0, columnspan=2, sticky="we", pady=8)
        cp.columnconfigure((0, 1), weight=1)
        ttk.Button(cp, text="Copiar sessionKey", command=self.copy_sk
                   ).grid(row=0, column=0, sticky="we", padx=(0, 4))
        ttk.Button(cp, text="Copiar JSON completo", command=self.copy_json
                   ).grid(row=0, column=1, sticky="we", padx=(4, 0))
        ttk.Button(frm, text="Abrir carpeta de backups", command=self.open_folder
                   ).grid(row=4, column=0, columnspan=2, sticky="we")

        ttk.Separator(frm).grid(row=5, column=0, columnspan=2, sticky="we", pady=12)

        st = ttk.Frame(frm); st.grid(row=6, column=0, columnspan=2, sticky="we")
        ttk.Label(st, text="Navegador:").grid(row=0, column=0, sticky="w", pady=3)
        self.browser = tk.StringVar(value=self.cfg.get("browser") or "auto")
        ttk.OptionMenu(st, self.browser, self.browser.get(), *BROWSERS,
                       command=lambda _: self.save()).grid(row=0, column=1, sticky="w", padx=6)
        ttk.Label(st, text="Cada:").grid(row=1, column=0, sticky="w", pady=3)
        self.days = tk.StringVar(value=str(self.cfg.get("days", 15)))
        ttk.OptionMenu(st, self.days, self.days.get(), *DAYS,
                       command=lambda _: self.save()).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(st, text="días").grid(row=1, column=2, sticky="w")
        ttk.Label(st, text="Conservar:").grid(row=2, column=0, sticky="w", pady=3)
        self.keep = tk.StringVar(value=str(self.cfg.get("keep", 3)))
        ttk.OptionMenu(st, self.keep, self.keep.get(), *KEEPS,
                       command=lambda _: self.save()).grid(row=2, column=1, sticky="w", padx=6)
        ttk.Label(st, text="backups").grid(row=2, column=2, sticky="w")

        self.log = ttk.Label(frm, foreground="#888")
        self.log.grid(row=7, column=0, columnspan=2, sticky="w", pady=(12, 0))
        self.refresh()

    # --- acciones ---
    def save(self):
        b = self.browser.get()
        self.cfg["browser"] = "" if b == "auto" else b
        self.cfg["days"] = int(self.days.get())
        self.cfg["keep"] = int(self.keep.get())
        save_cfg(self.cfg)
        self.log.config(text="Ajustes guardados.")
        self.refresh()

    def refresh(self):
        path, cookies = latest(self.cfg)
        if path:
            import datetime
            fecha = os.path.basename(path)[len("claude-cookies-"):-len(".json")]
            sk = session_key(cookies)
            n = len(cookies) if cookies else "?"
            nxt = datetime.datetime.fromtimestamp(
                os.path.getmtime(path) + self.cfg["days"] * 86400).strftime("%Y-%m-%d")
            self.status.config(text=(f"Última extracción:  {fecha}   ({n} cookies)\n"
                                     f"sessionKey:  {'✓ presente' if sk else '✗ falta'}\n"
                                     f"Próxima estimada:  {nxt}"))
        else:
            self.status.config(text="Sin backups todavía.\nDale a «Extraer ahora».")

    def extract(self):
        self.log.config(text="Extrayendo…"); self.root.update()
        r = subprocess.run([PY, os.path.join(DIR, "extract.py")],
                           capture_output=True, text=True)
        out = (r.stdout + r.stderr).strip().splitlines()
        self.log.config(text=out[-1] if out else "Listo.")
        if r.returncode != 0:
            messagebox.showerror("Error", r.stdout + r.stderr)
        self.refresh()

    def _copy(self, text, what):
        if not text:
            messagebox.showwarning("Nada que copiar", "No hay backup aún.")
            return
        self.root.clipboard_clear(); self.root.clipboard_append(text); self.root.update()
        messagebox.showinfo("Copiado", f"{what} en el portapapeles.\n"
                            "Pégalo antes de cerrar la ventana.")

    def copy_sk(self):
        _, cookies = latest(self.cfg)
        self._copy(session_key(cookies), "sessionKey")

    def copy_json(self):
        path, _ = latest(self.cfg)
        self._copy(open(path).read() if path else None, "JSON completo")

    def open_folder(self):
        open_path(out_folder(self.cfg))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
