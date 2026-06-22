# Instalador para Windows. Ejecutar en PowerShell:
#   powershell -ExecutionPolicy Bypass -File install.ps1
# Deja: dependencia, rclone.exe, config.json, tarea programada (diaria + al
# iniciar sesion, se auto-regula segun "days") y acceso directo a la GUI.
$ErrorActionPreference = "Stop"
$DIR = Split-Path -Parent $MyInvocation.MyCommand.Path
$BIN = Join-Path $env:USERPROFILE ".local\bin"
$CFGDIR = Join-Path $env:APPDATA "claude-cookie-backup"
New-Item -ItemType Directory -Force -Path $BIN, $CFGDIR | Out-Null

function Find-Python {
  foreach ($c in @("pythonw.exe","python.exe")) {
    $p = (Get-Command $c -ErrorAction SilentlyContinue)
    if ($p) { return $p.Source }
  }
  throw "No encontre Python en el PATH. Instala Python 3 (marcando 'Add to PATH')."
}
$PYW = Find-Python                     # pythonw para correr sin ventana de consola
$PY  = $PYW -replace "pythonw","python"

Write-Host "== Dependencia Python =="
& $PY -m pip install -q --upgrade browser_cookie3

Write-Host "== rclone =="
$RC = Join-Path $BIN "rclone.exe"
if (-not (Test-Path $RC) -and -not (Get-Command rclone -ErrorAction SilentlyContinue)) {
  $arch = if ([Environment]::Is64BitOperatingSystem) { "amd64" } else { "386" }
  Invoke-WebRequest "https://downloads.rclone.org/rclone-current-windows-$arch.zip" -OutFile "$env:TEMP\rclone.zip"
  Expand-Archive "$env:TEMP\rclone.zip" "$env:TEMP\rcl" -Force
  Copy-Item (Get-ChildItem "$env:TEMP\rcl" -Recurse -Filter rclone.exe)[0].FullName $RC -Force
}
if (-not (Test-Path $RC)) { $RC = (Get-Command rclone).Source }

if (-not (& $RC listremotes | Select-String "^gdrive:")) {
  Write-Host ">> Falta autorizar Drive. Corre:  $RC config"
  Write-Host "   crea remoto 'gdrive' (tipo drive, scope 1), autoriza, y re-corre este script."
  exit 1
}

Write-Host "== apunto el remoto a tu carpeta de Drive =="
$idFile = Join-Path $CFGDIR "folder_id"
$def = if (Test-Path $idFile) { Get-Content $idFile } else { "" }
$inp = Read-Host "Carpeta de Drive (URL o ID)$(if($def){" [$def]"})"
if (-not $inp) { $inp = $def }
$FOLDER_ID = ([regex]"[A-Za-z0-9_-]{20,}").Match($inp).Value
if (-not $FOLDER_ID) { throw "Falta el ID de la carpeta" }
Set-Content $idFile $FOLDER_ID
& $PY -c @"
import configparser, os, sys
p = os.path.expanduser('~/AppData/Roaming/rclone/rclone.conf')
if not os.path.exists(p): p = os.path.expanduser('~/.config/rclone/rclone.conf')
c = configparser.RawConfigParser(); c.read(p)
c['gdrive']['root_folder_id'] = '$FOLDER_ID'
with open(p,'w') as f: c.write(f)
"@

$DAYS = Read-Host "Cada cuantos dias [15]"; if (-not $DAYS) { $DAYS = "15" }
$KEEP = Read-Host "Cuantos backups conservar [3]"; if (-not $KEEP) { $KEEP = "3" }
$SHEET = Read-Host "URL del webhook del Sheet (vacio=no)"

$out = Join-Path $DIR "out"
New-Item -ItemType Directory -Force -Path $out | Out-Null
$cfg = @{ drive_folder=$out; rclone_remote="gdrive:"; sheet_webhook=$SHEET;
         keep=[int]$KEEP; days=[int]$DAYS; browser="" } | ConvertTo-Json
Set-Content (Join-Path $CFGDIR "config.json") $cfg
Write-Host "config.json escrito"

Write-Host "== tarea programada (diaria + al iniciar sesion) =="
$action  = New-ScheduledTaskAction -Execute $PYW -Argument "`"$DIR\extract.py`" --scheduled"
$tDaily  = New-ScheduledTaskTrigger -Daily -At 9am
$tLogon  = New-ScheduledTaskTrigger -AtLogOn
Register-ScheduledTask -TaskName "ClaudeCookieBackup" -Action $action `
  -Trigger $tDaily,$tLogon -Force | Out-Null

Write-Host "== acceso directo a la GUI =="
$lnk = Join-Path ([Environment]::GetFolderPath("StartMenu")) "Claude Cookie Backup.lnk"
$ws = New-Object -ComObject WScript.Shell
$s = $ws.CreateShortcut($lnk)
$s.TargetPath = $PYW; $s.Arguments = "`"$DIR\gui.py`""; $s.WorkingDirectory = $DIR
$s.Save()

Write-Host "== Listo en $env:COMPUTERNAME (Windows) =="
Write-Host "Extraer ahora:  & '$PY' '$DIR\extract.py'"
Write-Host "Interfaz:       & '$PYW' '$DIR\gui.py'"
