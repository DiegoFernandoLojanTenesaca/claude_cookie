<p align="center">
  <img src="assets/logo.svg" width="140" alt="claude-cookie-backup">
</p>

<h1 align="center">claude-cookie-backup</h1>

<p align="center"><b>Tu sesión de Claude, siempre contigo.</b><br>
Entra en cualquier computadora sin volver a iniciar sesión.</p>

---

Respalda **solo** tu sesión de **claude.ai** en tu propio Google Drive. Cambias de
equipo, viajas o se te daña la computadora y vuelves a entrar **en segundos**: sin
contraseñas, sin códigos de verificación, sin vincular tu correo en máquinas ajenas.

## ¿Te ha pasado esto?

- 🔄 **Cambiaste de computadora** y volver a entrar es un lío: verificación por correo,
  código, a veces ni abre a la primera.
- 🏢 Estás en una **PC del trabajo o prestada** y no quieres dejar tu Google/Gmail
  vinculado ahí.
- ✈️ **Viajas o sales del país** y necesitas tu sesión en otro equipo o en el celular.
- 💥 Se **dañó o perdiste** la computadora y no quieres quedarte sin acceso a tu cuenta.

## La solución

- ☁️ **Guarda tu sesión sola**, cada cierto tiempo, en **tu** Google Drive.
- ⚡ **La restauras en segundos** en cualquier navegador: copiar y pegar, y entras.
- 💻 **Windows, macOS y Linux** — y una **mini app para el celular**.
- 🔒 **Todo es tuyo:** tu Drive, tu cuenta. Nada pasa por servidores de terceros.

## Cómo funciona, en 10 segundos

1. **Instalas una vez** en la computadora donde usas Claude.
2. **Te olvidas:** respalda solo cada ciertos días y guarda los más recientes.
3. **¿Equipo nuevo?** Abres tu Drive, copias el respaldo y lo pegas con la extensión
   **EditThisCookie**. Listo, estás dentro.

## Instalar

| Sistema | Comando |
|---|---|
| **Linux / macOS** | `bash install.sh` |
| **Windows** | `powershell -ExecutionPolicy Bypass -File install.ps1` |

El instalador deja todo listo: respaldo automático, subida a tu Google Drive y una app
con interfaz para extraer y copiar cuando quieras. Te guía la primera vez para conectar
tu Drive.

## En el celular

`docs/` es una pequeña app web (PWA): la **instalas como icono** en el teléfono y, cuando
necesites entrar en otro lado, pegas el respaldo (lo abres desde tu Drive) y te da un
botón grande para **copiar tu sesión**. Funciona sin internet y no guarda nada fuera del
teléfono.

Para publicarla gratis: **Settings → Pages → rama `main`, carpeta `/docs`**.

## Restaurar tu sesión (en cualquier computadora)

1. Instala la extensión **EditThisCookie** en el navegador.
2. Abre el respaldo más reciente desde tu Drive y cópialo.
3. En claude.ai: EditThisCookie → **Import** → pega → guarda → recarga. Ya entraste.

## Privacidad

Tu respaldo es **tuyo y vive en tu Google Drive**. Este proyecto no envía nada a ningún
servidor ajeno. Eso sí: el respaldo es como **la llave de tu cuenta**, así que cuida
quién tiene acceso a esa carpeta. Si la quieres aún más protegida, se le puede añadir
cifrado.

<details>
<summary><b>Detalles técnicos</b> (para curiosos)</summary>

- Lee los cookies del navegador con `browser_cookie3` (descifra en Windows/DPAPI,
  macOS/Keychain y Linux/keyring) y exporta solo `sessionKey` y compañía en formato
  EditThisCookie. Si no hay sesión, **no sobrescribe** el último respaldo bueno.
- Elige **un solo navegador** (el de la sesión más fresca) entre Chrome, Brave,
  Chromium, Edge, Opera, Vivaldi y Firefox, y normaliza fechas a segundos.
- Sube a Google Drive con `rclone`; **cada computadora a su propia subcarpeta**
  (`gdrive:<nombre-pc>/`) para no pisarse, y conserva los últimos N.
- Toda la configuración en un solo `config.json`. El agendador (systemd / launchd /
  Programador de tareas) corre seguido y `extract.py --scheduled` se **auto-regula**
  según los días configurados.
- `extract.py` motor · `gui.py` interfaz · `install.sh` / `install.ps1` instaladores ·
  `sheet.gs` Google Sheet opcional · `docs/` la PWA.

</details>

## En una computadora nueva

Inicia sesión en claude.ai, baja el proyecto (zip desde tu Drive o `git clone`) y corre
el instalador. Mientras tanto, para entrar ya: abre tu respaldo desde el Drive y pégalo
con EditThisCookie.

## Lo que no hace

Necesita un navegador con tu sesión abierta para sacar el respaldo (nace ahí, no en un
servidor). Por defecto el respaldo va sin cifrar para que copiar y pegar sea fácil.
