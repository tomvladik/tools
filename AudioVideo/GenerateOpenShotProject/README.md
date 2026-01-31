# OpenShot Project Generator

Generate OpenShot video projects from audio files and photo sequences.

## Features

- Combines audio file with photo slideshow
- Auto-repeating photo sequence (loops if fewer photos than needed)
- Customizable photo duration (default: 2 minutes per photo)
- Crossfade transitions between photos
- YouTube-optimized settings (1080p, 30fps, H.264/AAC)

## Requirements

This script requires **libopenshot** to be installed. Since libopenshot is not available on PyPI for Windows, use one of these approaches:

### Option 1: VS Code Dev Container (Recommended)

1. Install the [Dev Containers](https://marketplace.visualstudio.com/items?itemName=ms-vscode-remote.remote-containers) extension
2. Open this workspace in VS Code
3. Press `Ctrl+Shift+P` and select **"Dev Containers: Reopen in Container"**
4. Wait for the container to build (includes libopenshot, FFmpeg, etc.)
5. Run the script inside the container

### Option 2: WSL2 or Linux

```bash
sudo apt-get update
sudo apt-get install libopenshot python3-openshot ffmpeg
python3 generate_openshot_project.py <audio> <photos_folder> <output.osp>
```

### Option 3: macOS

```bash
brew install libopenshot
python3 generate_openshot_project.py <audio> <photos_folder> <output.osp>
```

## Usage

```bash
python generate_openshot_project.py <audio_file> <photos_folder> <output_project>
```

### Examples

```bash
# Basic usage
python generate_openshot_project.py lecture.mp3 ./photos/ lecture_video.osp

# Custom photo duration (3 minutes per photo)
python generate_openshot_project.py --photo-duration 180 song.wav ./images/ project.osp

# Custom crossfade duration (1 second)
python generate_openshot_project.py --fade-duration 1 audio.mp3 ./photos/ output.osp

# Custom background color (red)
python generate_openshot_project.py --bg-color "#ff0000" audio.mp3 ./photos/ output.osp
```

### Command-line Options

```
positional arguments:
  audio_file            Path to audio file (WAV, MP3)
  photos_folder         Path to folder containing photos
  output_project        Path for output OpenShot project file

optional arguments:
  -h, --help            Show this help message
  --photo-duration      Duration of each photo in seconds (default: 120 = 2 minutes)
  --fade-duration       Crossfade duration in seconds (default: 2)
  --bg-color            Background color in hex (default: #000000 = black)
  --title               Title text for intro screen (default: Demo)
  --copyright           Copyright text (default: © 2024)
  --intro-duration      Intro screen duration in seconds (default: 180 = 3 minutes)
  --outro-duration      Outro screen duration in seconds (default: 60 = 1 minute)
  --no-youtube          Disable YouTube optimization
```

## Workflow

1. **Generate project**: Run the script to create an `.osp` file
2. **Open in OpenShot**: Launch OpenShot and open the generated `.osp` file
3. **Preview**: Play the timeline to review transitions
4. **Export**: Use OpenShot's export feature to render the final video

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

Use the Dev Container approach (Option 1 above) - it has all dependencies pre-installed.

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
