# MultiTool

A **PyQt6 desktop utility app** that brings together everyday tools for **media conversion**, **QR code generation**, **video processing**, **downloads**, and a few **Windows system helpers** in one place.

## ✨ Features

### QR tools
- Generate QR codes for:
  - URLs
  - WhatsApp links
  - Wi‑Fi credentials
- Export as `SVG`
- Optional circular QR styling

### Image tools
- Convert images to:
  - `ICO`
  - `PNG`
  - `JPEG`
  - `WEBP`
- View and strip **EXIF metadata**
- Extract frames from videos as images

### Video & audio tools
- Convert media to:
  - `MP3`
  - `MP4`
  - `AVI`
  - `MOV`
  - `WMV`
  - `WEBM`
- Trim clips and export to `MP3`, `GIF`, or `MP4`
- Stitch videos together
- Create and extract `MKV` files
- Resolution and frame-related utilities

### Downloader tools
- Download single videos or playlists using **yt-dlp**
- Choose from available formats before downloading
- Optional browser-cookie support for restricted content
- Optional **IDM** preference for MP4 downloads

### System tools
- GUI helper for running `XCOPY`

---

## 🖥️ Tech Stack

- **Python**
- **PyQt6**
- **Pillow**
- **qrcode**
- **ffmpeg / ffprobe**
- **yt-dlp**

---

## 📦 Requirements

This project is primarily **Windows-focused**.

Recommended setup:
- **Python 3.11+**
- `ffmpeg`, `ffprobe`, `ffplay`, `yt-dlp`, and `deno` must be **downloaded and installed separately**
- These external tools are **not included in this repository**
- Keep the executables either:
  - next to the app
  - inside `bin/`
  - or available in your system `PATH`

Optional extras:
- **Node.js** for improved `yt-dlp` JavaScript runtime support
- **Internet Download Manager (IDM)** for MP4 handoff
- `exifread` for EXIF viewing
- `pillow-heif` for HEIC/HEIF support

---

## 🚀 Getting Started

### 1. Download or clone the project
Place the project files on your machine, then open the folder in your terminal or IDE.

### 2. Install dependencies
```bash
pip install PyQt6 Pillow qrcode exifread pillow-heif pyinstaller
```

If you want downloader features available from the app, also install `yt-dlp` and ensure `ffmpeg` is available on your machine.

### 3. Run the app
```bash
python MultiTool.py
```

---

## 🏗️ Build the Executable

You can package the app with **PyInstaller** using the included scripts:

### PowerShell
```powershell
.\build.ps1
```

### Batch
```bat
build.bat
```

After a successful build, the executable is typically created at:

```text
dist/MultiTool.exe
```

---

## 📁 Project Structure

```text
MultiTool/
├── MultiTool.py
├── build.bat
├── build.ps1
├── Assets/
├── bin/
└── multitool/
    ├── app.py
    ├── helpers.py
    └── widgets/
```

---

## 📄 License

This project is licensed under the **GNU General Public License v3.0**.
See `License.txt` for details.

---

## 👤 Author

**Ali Qasem**

---
