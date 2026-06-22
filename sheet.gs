// === Apps Script para el Google Sheet ===
// 1. Abre tu Google Sheet (uno nuevo en blanco sirve).
// 2. Extensiones > Apps Script. Borra lo que haya y pega TODO esto.
// 3. Implementar > Nueva implementacion > engranaje > "Aplicacion web".
//      - Ejecutar como:  Yo
//      - Quien tiene acceso:  Cualquier usuario
// 4. Copia la "URL de la aplicacion web" que te da.
//      Esa URL es el SHEET_WEBHOOK que pide install.sh.
//
// Cada POST agrega una fila arriba y deja solo las KEEP mas nuevas.

var KEEP = 3;

// Visitar la URL en el navegador (GET) muestra "ok" = el despliegue esta vivo.
function doGet(e) {
  return ContentService.createTextOutput("ok");
}

function doPost(e) {
  var sheet = SpreadsheetApp.getActiveSpreadsheet().getSheets()[0];
  var d = JSON.parse(e.postData.contents);

  if (sheet.getLastRow() === 0) {
    sheet.appendRow(["fecha", "sessionKey", "json_completo"]);
  }
  sheet.insertRowBefore(2);
  sheet.getRange(2, 1, 1, 3).setValues([[d.fecha, d.sessionKey, d.json]]);

  var last = sheet.getLastRow();          // incluye la fila de encabezado
  if (last > KEEP + 1) {
    sheet.deleteRows(KEEP + 2, last - (KEEP + 1));
  }
  return ContentService.createTextOutput("ok");
}
