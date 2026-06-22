#!/usr/bin/env python3
"""Interfaz minima para claude-cookie-backup (Tkinter, sin dependencias).
Extraer a demanda, copiar el cookie para pegarlo en otra PC, cambiar cada
cuantos dias corre y abrir la carpeta."""
import os, re, glob, json, subprocess
import tkinter as tk
from tkinter import messagebox

DIR = os.path.dirname(os.path.abspath(__file__))
SERVICE = os.path.expanduser("~/.config/systemd/user/claude-cookies.service")
TIMER = os.path.expanduser("~/.config/systemd/user/claude-cookies.timer")


def out_folder():
    """Lee DRIVE_FOLDER del service; si no, usa out/ del proyecto."""
    try:
        m = re.search(r"DRIVE_FOLDER=(.+)", open(SERVICE).read())
        if m and m.group(1).strip():
            return m.group(1).strip()
    except FileNotFoundError:
        pass
    return os.path.join(DIR, "out")


def latest():
    """(ruta, lista_cookies) del backup mas nuevo, o (None, None)."""
    files = sorted(glob.glob(os.path.join(out_folder(), "claude-cookies-*.json")))
    if not files:
        return None, None
    return files[-1], json.load(open(files[-1]))


def session_key(cookies):
    return next((c["value"] for c in cookies if c["name"] == "sessionKey"), None)


def next_run():
    try:
        out = subprocess.check_output(
            ["systemctl", "--user", "list-timers", "claude-cookies.timer",
             "--no-pager"], text=True)
        for line in out.splitlines():
            if "claude-cookies" in line:
                return "en " + line.split()[3] + " " + line.split()[4]
    except Exception:
        pass
    return "?"


class App:
    def __init__(self, root):
        self.root = root
        root.title("Claude · backup de cookies")
        root.resizable(False, False)
        pad = {"padx": 12, "pady": 6}

        self.status = tk.Label(root, justify="left", anchor="w", font=("", 11))
        self.status.grid(row=0, column=0, columnspan=2, sticky="we", **pad)

        tk.Button(root, text="⟳  Extraer ahora", command=self.extract,
                  height=2).grid(row=1, column=0, columnspan=2, sticky="we", **pad)

        tk.Button(root, text="Copiar sessionKey", command=self.copy_sk
                  ).grid(row=2, column=0, sticky="we", **pad)
        tk.Button(root, text="Copiar JSON completo", command=self.copy_json
                  ).grid(row=2, column=1, sticky="we", **pad)

        tk.Button(root, text="Abrir carpeta", command=self.open_folder
                  ).grid(row=3, column=0, sticky="we", **pad)
        # selector de intervalo
        box = tk.Frame(root); box.grid(row=3, column=1, sticky="we", **pad)
        tk.Label(box, text="cada").pack(side="left")
        self.days = tk.StringVar(value=self.current_days())
        tk.OptionMenu(box, self.days, "10", "15", "20", "30").pack(side="left")
        tk.Label(box, text="días").pack(side="left")
        tk.Button(box, text="Aplicar", command=self.apply_days).pack(side="left", padx=4)

        self.refresh()

    def current_days(self):
        try:
            m = re.search(r"OnUnitActiveSec=(\d+)d", open(TIMER).read())
            return m.group(1) if m else "10"
        except FileNotFoundError:
            return "10"

    def refresh(self):
        path, cookies = latest()
        if path:
            fecha = os.path.basename(path).replace("claude-cookies-", "").replace(".json", "")
            sk = session_key(cookies)
            estado = (f"Última extracción: {fecha}   ({len(cookies)} cookies)\n"
                      f"sessionKey: {'OK' if sk else 'FALTA'}\n"
                      f"Próxima automática: {next_run()}")
        else:
            estado = "Sin backups todavía.\nDale a «Extraer ahora»."
        self.status.config(text=estado)

    def extract(self):
        self.status.config(text="Extrayendo…"); self.root.update()
        r = subprocess.run(["systemctl", "--user", "start", "claude-cookies"],
                           capture_output=True, text=True)
        if r.returncode != 0:
            messagebox.showerror("Error", r.stderr or "Falló la extracción")
        self.refresh()

    def _copy(self, text, what):
        if not text:
            messagebox.showwarning("Nada que copiar", "No hay backup aún.")
            return
        self.root.clipboard_clear(); self.root.clipboard_append(text); self.root.update()
        messagebox.showinfo("Copiado", f"{what} en el portapapeles.\n"
                            "Pégalo antes de cerrar esta ventana.")

    def copy_sk(self):
        _, cookies = latest()
        self._copy(session_key(cookies) if cookies else None, "sessionKey")

    def copy_json(self):
        path, cookies = latest()
        self._copy(open(path).read() if path else None, "JSON completo")

    def open_folder(self):
        subprocess.Popen(["xdg-open", out_folder()])

    def apply_days(self):
        d = self.days.get()
        try:
            txt = open(TIMER).read()
            txt = re.sub(r"OnUnitActiveSec=\d+d", f"OnUnitActiveSec={d}d", txt)
            open(TIMER, "w").write(txt)
            subprocess.run(["systemctl", "--user", "daemon-reload"])
            subprocess.run(["systemctl", "--user", "restart", "claude-cookies.timer"])
            messagebox.showinfo("Listo", f"Ahora corre cada {d} días.")
            self.refresh()
        except Exception as e:
            messagebox.showerror("Error", str(e))


if __name__ == "__main__":
    root = tk.Tk()
    App(root)
    root.mainloop()
