# OpenShot Project Generator

Generate OpenShot video projects from audio files and photo sequences.

## Features

- Combines audio file with photo slideshow
- Auto-repeating photo sequence (loops if fewer photos than needed)
- Customizable photo duration (default: 2 minutes per photo)
- Crossfade transitions between photos
- YouTube-optimized settings (1080p, 30fps, H.264/AAC)

## Requirements

**Essential:**
- `ffmpeg` and `ffprobe` (required for all rendering)

**Optional:**
- `python3-openshot` (to create `.osp` project files or use libopenshot Timeline rendering)
- `Pillow` (for `make_test_data.py` to create numbered test images)

### Setup Options

#### Option 1: VS Code Dev Container (Recommended)

1. Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension
2. Open this workspace in VS Code
3. Press `Ctrl+Shift+P` and select **"Dev Containers: Reopen in Container"**
4. Wait for the container to build (includes libopenshot, FFmpeg, etc.)
5. Run the script inside the container

#### Option 2: Linux/WSL

```bash
sudo apt-get install ffmpeg python3-openshot python3-pip
pip install Pillow
```

#### Option 3: macOS

```bash
brew install ffmpeg libopenshot
pip install Pillow
```

#### Option 4: Render video without `.osp` project files

You can render MP4 videos directly using `--export-video` without installing libopenshot — FFmpeg alone is sufficient.


## Usage

```bash
python generate_openshot_project.py <audio_file> <photos_folder> <output_project>
```

### Examples

#### Create OpenShot Project File (.osp) - Full Feature Support

**Supported options:** `--photo-duration`, `--fade-duration`, `--bg-color`, `--youtube`/`--no-youtube`, `--title`, `--copyright`, `--intro-duration`, `--outro-duration`, `--trim-start`, `--trim-end`, `--no-repeat`

```bash
# Basic usage (requires python3-openshot)
python generate_openshot_project.py lecture.mp3 ./photos/ lecture_video.osp

# Custom photo duration (3 minutes per photo) with title/copyright
python generate_openshot_project.py --photo-duration 180 --title "My Video" --copyright "© 2026 Me" song.wav ./images/ project.osp

# Custom crossfade duration (1 second)
python generate_openshot_project.py --fade-duration 1 audio.mp3 ./photos/ output.osp

# Custom background color (red) and longer intro, trim audio start/end
python generate_openshot_project.py --bg-color "#ff0000" --intro-duration 300 --trim-start 5 --trim-end 2 audio.mp3 ./photos/ output.osp
```

#### Render Video Directly (MP4) - Limited Feature Set

**Supported options:** `--photo-duration`, `--fade-duration`, `--bg-color`, `--youtube`/`--no-youtube`, `--intro-duration`, `--outro-duration`, `--no-repeat`, `--test-run`, `--use-libopenshot`, `--save-osp`, `--trim-start`, `--trim-end`

**NOT supported with `--export-video`:** `--title`, `--copyright`

```bash
# Direct FFmpeg rendering (no .osp file, only needs ffmpeg)
python generate_openshot_project.py --export-video lecture.mp3 ./photos/ output.mp4

# Test mode: fast draft rendering at 320x200@10fps
python generate_openshot_project.py --export-video --test-run song.wav ./images/ output.mp4

# Trim audio from start/end and render
python generate_openshot_project.py --export-video --trim-start 5 --trim-end 2 audio.mp3 ./photos/ output.mp4

# Also create .osp project file alongside the video (useful for later editing)
python generate_openshot_project.py --export-video --save-osp audio.mp3 ./photos/ output.mp4

# Use libopenshot Timeline (slower but like editing in OpenShot)
python generate_openshot_project.py --export-video --use-libopenshot audio.mp3 ./photos/ output.mp4

# Don't repeat photos; extend each one to fill the slideshow duration
python generate_openshot_project.py --export-video --no-repeat song.wav ./images/ output.mp4
```

#### Utilities

```bash
# Check installed tool versions
python generate_openshot_project.py --versions
```
### Command-line Options

```
positional arguments:
  audio_file            Path to audio file (WAV, MP3)
  photos_folder         Path to folder containing photos
  output_project        Path for output file (.osp for project, .mp4/.mkv for video)

optional arguments:
  -h, --help            Show this help message and exit
  --versions            Print current versions of key utilities and exit
  --export-video        Render video directly instead of creating .osp project file
  --save-osp            Also save .osp project file when using --export-video
  --use-libopenshot     Use libopenshot Timeline for rendering (may be unstable; requires --export-video)
  --test-run            Fast draft mode: render at 320x200@10fps for quick testing (requires --export-video)
  --no-repeat           Do not repeat images; equally prolong each photo to cover audio length
  --photo-duration      Duration of each photo in seconds (default: 120 = 2 minutes)
  --fade-duration       Crossfade transition duration in seconds (default: 2.5)
  --bg-color            Background color in hex format (default: #c7958b). Examples: #ffffff (white), #ff0000 (red)
  --youtube             Use YouTube-optimized export settings (default; 1080p 30fps H.264/AAC)
  --no-youtube          Disable YouTube optimization
  --title               Title text for intro screen (default: Demo)
  --copyright           Copyright text for screens (default: © 2024)
  --intro-duration      Intro screen duration in seconds (default: 180 = 3 minutes)
  --outro-duration      Outro screen duration in seconds (default: 60 = 1 minute)
  --trim-start          Trim audio from the beginning in seconds (default: 0.0)
  --trim-end            Trim audio from the end in seconds (default: 0.0)
```

## Workflow

### Option A: Create `.osp` Project File (Edit in OpenShot) — Full Features

**Best for:** Interactive editing, text overlays (title/copyright), precise audio trimming

1. **Generate project**: `python generate_openshot_project.py audio.mp3 ./photos/ output.osp`
2. **Open in OpenShot**: Launch OpenShot and open the generated `.osp` file
3. **Preview**: Play the timeline to review transitions and make edits
4. **Export**: Use OpenShot's export feature to render the final video

**Features available:**
- ✅ Photo duration, crossfade duration, background color
- ✅ Intro/outro screens with duration control
- ✅ Title and copyright text overlays
- ✅ Audio trimming (start/end)
- ✅ Full OpenShot editing capabilities after export

### Option B: Render Video Directly (MP4) — Fast, Limited Features

**Best for:** Quick rendering, automated pipelines, Windows (no libopenshot needed)

1. **Generate video**: `python generate_openshot_project.py --export-video audio.mp3 ./photos/ output.mp4`
2. **Done**: Final video is ready to use

**Features available:**
- ✅ Photo duration, crossfade duration, background color
- ✅ Intro/outro screens with duration control
- ✅ Audio trimming (start/end)
- ❌ Title/copyright text overlays (not supported)
- ⚠️ Limited editing: can use `--save-osp` to create `.osp` for further editing

**Note:** Direct rendering is faster and doesn't require libopenshot.

## File Structure

```
.devcontainer/
  ├── devcontainer.json    # VS Code container config
  └── Dockerfile           # Container image definition
docker-compose.yml         # Docker Compose file (optional)
generate_openshot_project.py  # Main script
README.md                  # This file
```

## Supported Photo Formats

- JPEG (.jpg, .jpeg)
- PNG (.png)
- BMP (.bmp)
- GIF (.gif)
- TIFF (.tiff)

Photos are processed in alphabetical order.

## Supported Audio Formats

- WAV (.wav)
- MP3 (.mp3)
- FLAC (.flac)
- OGG (.ogg)
- Any format supported by FFmpeg

## Troubleshooting

### "ModuleNotFoundError: No module named 'openshot'"

**If creating `.osp` project files:** Use the Dev Container approach or install `python3-openshot` on Linux/macOS.

**If rendering video directly:** Use `--export-video` instead — FFmpeg alone is sufficient and works on Windows without libopenshot.

### "Error: FFmpeg/FFprobe not found"

Install FFmpeg:
- Linux: `sudo apt-get install ffmpeg`
- macOS: `brew install ffmpeg`
- Windows: Download from https://ffmpeg.org/download.html

### Project file won't open in OpenShot

Make sure you're using a recent version of OpenShot (2.6+). Delete the file and regenerate if it was created on an older version of this script.

## Notes

- Audio duration determines total video length
- If intro + outro exceeds audio duration, an error will occur
- Photos repeat in sequence if there aren't enough to fill the duration
- Crossfade transitions overlap clips for smooth transitions
