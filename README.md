# DAV Video Converter

A lightweight DAV to MP4 converter with two options:

- Recommended: Python desktop UI (`desktop_converter.py`)
- Optional: Browser UI (`browser version_failed/index.html`)

## Recommended: Python desktop app

This avoids browser worker/runtime limits and is the most reliable option for `.dav`.

### Setup

```bash
cd "/Users/aay/Desktop/VibeApps/video converter"
pip install -r requirements.txt
```

If you see `ModuleNotFoundError: No module named '_tkinter'` on macOS Homebrew Python:

```bash
brew install python-tk@3.11
```

### Run

```bash
cd "/Users/aay/Desktop/VibeApps/video converter"
python desktop_converter.py
```

### Features

- Pick `.dav` file with a simple native window
- One-click conversion to H.264/AAC MP4
- Progress bar and status updates
- Automatic retry without audio stream when needed

## Browser app (optional)

The browser version is still included, but can fail in restricted browser contexts.

### Why this approach

- No Python packaging needed for this version
- No backend server required
- Runs locally in browser using ffmpeg.wasm

### How to run

1. Open `browser version_failed/index.html` directly in Chrome, Edge, or Safari, or serve it with a local static server.
2. Select or drop a `.dav` file.
3. Click **Convert to MP4**.
4. Click **Download MP4** when conversion completes.

### Notes

- First conversion takes longer because FFmpeg engine loads.
- Very large files can be slow and memory-heavy in browser.
- Some encrypted/vendor-proprietary DAV files may fail to decode.
- If the UI stays on loading/progress 1% for a long time, use the Python desktop app above.

## Native ffmpeg fallback (CLI)

Use terminal conversion for best reliability on macOS:

```bash
cd "/Users/aay/Desktop/VibeApps/video converter"
ffmpeg -y -i "NVR.dav" -c:v libx264 -preset veryfast -crf 23 -c:a aac -b:a 96k -movflags +faststart "NVR_converted_native.mp4"
```

This command was tested in this workspace and successfully produced an MP4 from NVR.dav.

## Optional Python route

If you later want a Python desktop app, you can build one with Tkinter + ffmpeg-python and use the same conversion logic with a system ffmpeg binary.
