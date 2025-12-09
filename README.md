# Media Converter (HEIC & Video)
 
A simple, fast, and multi-threaded Python script to convert bulk HEIC images to JPEG, and videos (MOV, etc.) to MP4.

## Installation
python heic2jpg.py "C:\path\to\your\heic\images"
```

**Specify Output Directory:**
```bash
python heic2jpg.py "C:\input" -o "C:\output"
```

**Adjust Quality (1-100, default 95):**
```bash
python heic2jpg.py "C:\input" -q 80
```

## Features
- **Video Support**: Automatically converts `.mov` and other video formats to `.mp4` (H.264).
- **Fast**: Uses multiple CPU cores to process images in parallel.
- **Progress Bar**: Shows real-time progress.
- **Simple**: Minimal dependencies and easy CLI.

## Building from Source (EXE)

To create a standalone executable:
```bash
pip install pyinstaller
pyinstaller --onefile --name heic2jpg heic2jpg.py
```
The executable will be located in the `dist` folder.
