/**
 * GOOGLE APPS SCRIPT: Uploader File ke Google Drive
 * Versi 2 — Support nested subfolder (platform/outlet)
 *
 * CARA DEPLOY:
 * 1. Buka https://script.google.com → Project baru
 * 2. Paste kode ini, simpan
 * 3. Deploy → New deployment → Web App
 *    - Execute as: Me
 *    - Who has access: Anyone
 * 4. Copy URL /exec → paste ke .env sebagai GDRIVE_APPSCRIPT_URL
 *
 * PAYLOAD yang diterima (JSON POST):
 * {
 *   "fileName"    : "nama_file.xlsx",
 *   "fileBase64"  : "<base64 string>",
 *   "mimeType"    : "application/vnd.openxmlformats-...",
 *   "folderId"    : "id_folder_induk",          // opsional
 *   "subFolderName" : "GR",                     // opsional — level 1 (platform)
 *   "outletFolderName" : "nama_outlet"          // opsional — level 2 (outlet)
 * }
 */

// ID folder induk default (dapat di-override via payload)
var defaultFolderId = "1qrWCVAOoM6Hh1N6luvdhxeN-pcLNCJgU";

function doPost(e) {
  try {
    if (!e || !e.postData || !e.postData.contents) {
      return buildResponse("error", "Request body kosong atau tidak valid.");
    }

    var data = JSON.parse(e.postData.contents);
    var folderId        = data.folderId        || defaultFolderId;
    var subFolderName   = data.subFolderName   || "";   // level 1: GR / S / GO
    var outletFolder    = data.outletFolderName || "";  // level 2: nama outlet
    var fileName        = data.fileName;
    var fileBase64      = data.fileBase64;
    var mimeType        = data.mimeType || "application/octet-stream";

    if (!fileName || !fileBase64) {
      return buildResponse("error", "Parameter 'fileName' atau 'fileBase64' tidak ditemukan.");
    }

    // Decode base64
    var decodedBytes = Utilities.base64Decode(fileBase64);
    var blob = Utilities.newBlob(decodedBytes, mimeType, fileName);

    // ── Navigasi ke folder induk ──────────────────────────
    var parentFolder;
    if (folderId && folderId.trim() !== "" && folderId !== "YOUR_DEFAULT_FOLDER_ID") {
      try {
        parentFolder = DriveApp.getFolderById(folderId);
      } catch (fErr) {
        return buildResponse("error", "Folder ID '" + folderId + "' tidak ditemukan: " + fErr.toString());
      }
    } else {
      parentFolder = DriveApp.getRootFolder();
    }

    // ── Level 1: subfolder platform (GR / S / GO) ─────────
    var folder = parentFolder;
    var subFolderCreated = false;
    if (subFolderName && subFolderName.trim() !== "") {
      var sf = parentFolder.getFoldersByName(subFolderName);
      if (sf.hasNext()) {
        folder = sf.next();
      } else {
        folder = parentFolder.createFolder(subFolderName);
        subFolderCreated = true;
      }
    }

    // ── Level 2: subfolder outlet ─────────────────────────
    var outletFolderCreated = false;
    if (outletFolder && outletFolder.trim() !== "") {
      var of = folder.getFoldersByName(outletFolder);
      if (of.hasNext()) {
        folder = of.next();
      } else {
        folder = folder.createFolder(outletFolder);
        outletFolderCreated = true;
      }
    }

    // ── Hapus file lama dengan nama sama (hindari duplikasi) ─
    var existingFiles = folder.getFilesByName(fileName);
    var deleteCount = 0;
    while (existingFiles.hasNext()) {
      existingFiles.next().setTrashed(true);
      deleteCount++;
    }

    // ── Simpan file ───────────────────────────────────────
    var newFile = folder.createFile(blob);

    return buildResponse("success", "File berhasil diunggah ke Google Drive.", {
      fileId: newFile.getId(),
      url: newFile.getUrl(),
      fileName: fileName,
      folderId: folder.getId(),
      platformFolder: subFolderName || null,
      outletFolder: outletFolder || null,
      subFolderCreated: subFolderCreated,
      outletFolderCreated: outletFolderCreated,
      deletedOldVersions: deleteCount
    });

  } catch (error) {
    return buildResponse("error", "Kesalahan di Apps Script: " + error.toString());
  }
}

function buildResponse(status, message, dataDetails) {
  var output = { status: status, message: message };
  if (dataDetails) {
    for (var key in dataDetails) {
      if (dataDetails.hasOwnProperty(key)) output[key] = dataDetails[key];
    }
  }
  return ContentService.createTextOutput(JSON.stringify(output))
                       .setMimeType(ContentService.MimeType.JSON);
}

// GET — cek status Web App
function doGet(e) {
  return ContentService.createTextOutput(JSON.stringify({
    status: "success",
    message: "Apps Script Uploader v2 aktif. Mendukung nested folder (platform/outlet)."
  })).setMimeType(ContentService.MimeType.JSON);
}
