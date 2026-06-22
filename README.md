<p align="center">
  <img src="assets/logo.svg" width="140" alt="claude-cookie-backup">
</p>

<h1 align="center">claude-cookie-backup</h1>

<p align="center"><em>Respaldo automático de tu sesión de claude.ai en Google Drive.</em></p>

Saca automáticamente los cookies de tu sesión web de **claude.ai** y los respalda
en **Google Drive**, para poder reabrir tu cuenta en otra PC (o si esta se daña /
sales del país) sin contraseña: importas los cookies con **EditThisCookie** y entras.

Corre solo cada N días (y a demanda), rota los backups, tiene interfaz gráfica y se
reinstala en una máquina nueva en minutos.

---

## Cómo funciona

```
Chrome (sesión claude.ai)
        │  browser_cookie3 lee la BD de cookies + KWallet
        ▼
   extract.py  ──► out/claude-cookies-FECHA_HORA.json   (local, rota a 3)
        │
        ├─ rclone sync ──► Google Drive: gdrive:<nombre-pc>/   (rota a 3 por PC)
        └─ (opcional) POST ──► Google Sheet (Apps Script)
        ▲
   agendador (systemd / launchd / Task Scheduler) corre diario;
   extract.py --scheduled se auto-regula según "days" en config.json
```

- **Solo `sessionKey` importa** para reabrir la sesión; los cookies de Cloudflare
  (`__cf_bm`, `_cfuvid`) se regeneran solos. Por eso el respaldo periódico tiene
  sentido: `sessionKey` caduca (~28 días) y hay que refrescarlo.
- El script **aborta sin sobrescribir** si no encuentra `sessionKey` (sesión cerrada
  o lectura fallida), así nunca guarda un backup vacío encima del bueno.

> ⚠️ **El cookie nace en el navegador donde inicias sesión.** La extracción SIEMPRE
> corre en la PC donde usas Claude — un servidor pelado no tiene sesión que leer.
> Lo que sobrevive a perder la PC es el cookie ya subido a Drive (válido ~28 días)
> y este proyecto (zipeado en Drive).

---

## Seguridad

- A Drive sube el JSON **en texto plano** (sin cifrado — decisión deliberada para que
  sea fácil copiar/pegar). El `sessionKey` = acceso total a tu cuenta: cuida quién
  ve esa carpeta de Drive y el token de rclone (`~/.config/rclone/rclone.conf`).
- Nunca se versiona ningún cookie ni token: `out/` y la config de rclone están fuera
  del repo (ver `.gitignore`).
- Si alguna vez quieres cifrado en reposo, se añade con `gpg`/`age` antes del `sync`.

---

## Requisitos

- **Linux, Windows o macOS.**
- **Chrome** (o Brave/Chromium/Edge/Opera/Vivaldi/Firefox) con tu sesión de claude.ai abierta.
- Python 3 con `tkinter` (para la GUI) — incluido en los instaladores de Windows/macOS
  y en la mayoría de distros Linux.
- Keyring desbloqueado (el navegador cifra su clave de cookies ahí): KWallet/GNOME
  Keyring en Linux, Keychain en macOS, DPAPI en Windows. En Linux se recomienda el
  keyring **con contraseña vacía** para que el agendado no se trabe pidiéndola.

Los instaladores ponen lo demás (`browser_cookie3` y `rclone`).

---

## Instalación

| Sistema | Comando |
|---|---|
| **Linux / macOS** | `bash install.sh` |
| **Windows** | `powershell -ExecutionPolicy Bypass -File install.ps1` |

El instalador es idempotente (repítelo para reconfigurar) y hace todo:

1. Instala `browser_cookie3` y `rclone`.
2. Si no existe el remoto `gdrive`, te dice el `rclone config` para autorizarlo
   (`tipo: drive · scope: 1 · autorizar en el navegador`). Eso necesita tu navegador
   una vez; luego re-corres el instalador.
3. Apunta el remoto a tu carpeta de Drive (pegas la URL o el ID; se guarda local).
4. Pregunta cada cuántos días, cuántos backups conservar y (opcional) la URL del Sheet,
   y escribe `config.json`.
5. Registra el **agendado** (systemd/launchd/Task Scheduler) y un **acceso a la GUI**.

Toda la configuración vive en un solo `config.json`
(`~/.config/claude-cookie-backup/` o `%APPDATA%\claude-cookie-backup\`), que comparten
el script, la GUI y el agendador.

---

## Uso

### Interfaz gráfica
Búscala en el menú como **«Claude · Cookie Backup»**, o:
```bash
python3 gui.py
```
Botones: **Extraer ahora**, **Copiar sessionKey**, **Copiar JSON completo**
(para pegar en EditThisCookie), **Abrir carpeta**, **selector de navegador**, y
selectores de **intervalo** y **cuántos conservar** (se guardan en `config.json`).

### Línea de comandos
```bash
python3 extract.py              # extraer YA (a demanda, en cualquier OS)
python3 extract.py --scheduled  # lo que corre el agendador: salta si es muy reciente
python3 extract.py --self-test  # chequear la lógica
# ver el agendado: systemctl --user list-timers (Linux) · schtasks (Windows) · launchctl list (mac)
```

---

## Programación y reinicios

El agendador es **«tonto»** (corre seguido) y el script se **auto-regula**: con
`--scheduled`, `extract.py` salta si el último backup es más nuevo que `days`. Así
cambiar el intervalo es solo editar `config.json` — no hay que tocar el agendador.

- **Linux (systemd --user):** timer diario + `OnBootSec=5min` (corre tras cada arranque);
  `enabled`, sobrevive reinicios.
- **macOS (launchd):** `RunAtLoad` (al iniciar sesión) + `StartInterval` 24 h.
- **Windows (Task Scheduler):** disparadores *diario* + *al iniciar sesión*.
- **Caveat inofensivo:** si una corrida cae con el keyring aún bloqueado (antes de
  iniciar sesión), aborta limpia y la siguiente sale bien. No se pierde nada.

---

## Multiplataforma

El motor (`extract.py`) y la GUI (`gui.py`) son los mismos en los tres sistemas
(`browser_cookie3` descifra en Windows/DPAPI, macOS/Keychain y Linux/keyring; `rclone`
es multiplataforma). Solo cambia el **agendador** y el **acceso directo**, que cada
instalador resuelve por su sistema.

---

## Multi-PC

Instala lo mismo en cada PC donde uses Claude. Cada una sube a **su propia subcarpeta**
`gdrive:<hostname>/`, así los `rclone sync` (que espejan) **no se borran entre sí** y
si una PC se daña, las demás siguen sacando cookies frescos.

---

## PC nueva (o si se daña esta)

1. Inicia sesión en claude.ai en **Chrome**.
2. Baja `claude-cookie-backup.zip` desde tu carpeta de Drive (o `git clone` del repo).
3. `bash install.sh` (te guía con el `rclone config` si falta autorizar Drive).

Mientras tanto, para **entrar ya**: en Drive → subcarpeta de la PC vieja → abre el
`.json` más nuevo → cópialo → pégalo en EditThisCookie (ver abajo).

---

## Restaurar la sesión en otra PC

1. Instala la extensión **EditThisCookie** (v3) en el navegador.
2. Consigue el JSON:
   - **Drive:** abre el `.json` más nuevo de tu carpeta y copia todo.
   - **Sheet** (si lo configuraste): copia la celda `json_completo` de la fila de arriba.
3. En claude.ai → EditThisCookie → **Import** → pega el JSON → guarda.
4. Recarga la página. Estás dentro.

---

## Google Sheet (opcional)

Para copiar/pegar el cookie desde el móvil. Pega `sheet.gs` en el Apps Script de un
Google Sheet, despliégalo como app web («Cualquier usuario») y pon esa URL en
`install.sh`. Cada extracción agrega una fila (fecha · sessionKey · JSON completo) y
deja las 3 más nuevas.

---

## App móvil (PWA)

`web/` es una mini app (HTML estático, sin backend) para tener el cookie a mano en el
móvil. **Pegas el JSON** del backup (lo abres desde Drive en el teléfono), y te da
botón grande de **Copiar sessionKey** / **Copiar JSON completo**, muestra cuándo
caduca, lo recuerda en el dispositivo (`localStorage`) y funciona offline. Se instala
como icono ("Añadir a pantalla de inicio").

Para publicarla: activa **GitHub Pages** sobre la carpeta `/web` (Settings → Pages), o
ábrela local. No expone nada: el `sessionKey` nunca sale del teléfono.

> Decisión de diseño: que el móvil *jale solo* el cookie exigiría una URL pública con
> tu sesión = acceso total a la cuenta. Por eso es **pegar-y-copiar**, no auto-fetch.
> El import de cookies en sí se hace en un navegador de escritorio con EditThisCookie.

---

## Rotación

Cada corrida escribe `claude-cookies-AAAA-MM-DD_HH-MM-SS.json` y borra los viejos
dejando los `KEEP` más nuevos (default 3), tanto en local como en la subcarpeta de
Drive de esa PC. El Sheet hace lo mismo con sus filas.

---

## Archivos

| Archivo | Qué hace |
|---|---|
| `extract.py` | Motor: lee cookies, arma el JSON (formato EditThisCookie), guarda local, rota, sube a Drive y/o al Sheet. `--scheduled` se auto-regula; `--self-test` chequea. |
| `gui.py` | Interfaz Tkinter/ttk multiplataforma: extraer, copiar, navegador, intervalo, conservar. |
| `install.sh` | Instalador Linux (systemd) y macOS (launchd). |
| `install.ps1` | Instalador Windows (Task Scheduler + acceso directo). |
| `sheet.gs` | Apps Script para el Google Sheet opcional. |
| `web/` | Mini PWA para el móvil (pegar-y-copiar, offline, instalable). |
| `out/` | Backups locales (ignorado por git). |

Config (no versionada): `config.json` en `~/.config/claude-cookie-backup/` (o
`%APPDATA%` en Windows).

---

## Detalles técnicos (gotchas)

- **`browser_cookie3` mezcla unidades:** devuelve `expires` en **segundos** para
  Chrome pero en **milisegundos** para Firefox. Por eso `extract.py` elige **un solo
  navegador** (el del `sessionKey` con expiración más tardía) y normaliza a segundos
  (`>1e11` ⇒ ms ⇒ /1000). Así el set es consistente y de una sola sesión.
- Salida con `sort_keys=True` para igualar el orden de campos de EditThisCookie; las
  cookies de sesión omiten `expirationDate`.
- El agendado usa `sys.executable` (no el shim de pyenv) para que lo encuentre.
- `rclone sync` por-PC usa `socket.gethostname()` como subcarpeta.
- Config única en `config.json`; el agendador corre `extract.py --scheduled`, que salta
  si el último backup tiene menos de `days` días (auto-regulación sin tocar el agendador).

---

## Reconfigurar / desinstalar

Reconfigurar: vuelve a correr el instalador, o cambia los valores en la GUI / `config.json`.

```bash
# Linux
systemctl --user disable --now claude-cookies.timer
rm ~/.config/systemd/user/claude-cookies.{service,timer}
rm ~/.local/share/applications/claude-cookie-backup.desktop
# macOS
launchctl unload ~/Library/LaunchAgents/com.claudecookies.backup.plist && \
  rm ~/Library/LaunchAgents/com.claudecookies.backup.plist
# Windows (PowerShell)
Unregister-ScheduledTask -TaskName ClaudeCookieBackup -Confirm:$false
```

---

## Limitaciones

- Necesita un navegador con sesión activa para extraer (no funciona «solo en un
  servidor»). Para 24/7 independiente de tu PC harías falta un VPS con un navegador
  real logueado, con el riesgo de que Anthropic marque el login desde datacenter.
- Sin cifrado en reposo (por decisión).
