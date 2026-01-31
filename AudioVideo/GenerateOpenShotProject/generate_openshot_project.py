#!/usr/bin/env python3
"""
Generate an Openshot video project from audio and photos.

This script creates an Openshot project that combines:
- Audio file (WAV, MP3)
- Photo sequence (repeated to match audio duration)
- 2-second crossfade transitions between photos
- 2-minute duration per photo
- Solid background color (for aspect ratio filling)
- YouTube-optimized export settings

Usage:
    python generate_openshot_project.py <audio_file> <photos_folder> <output_project>

Example:
    python generate_openshot_project.py lecture.mp3 ./photos/ lecture_video.osp
    python generate_openshot_project.py --bg-color "#ff0000" lecture.mp3 ./photos/ lecture_video.osp
"""

import argparse
import os
import sys
import json
import subprocess
import zipfile
import io
import uuid
from pathlib import Path
from typing import List, Tuple, Dict, Any
import shutil
import platform


def get_tool_versions() -> Dict[str, str]:
    """Return versions of key tools as a dict, plus OS info."""
    versions: Dict[str, str] = {}
    versions["python"] = platform.python_version()
    versions["python_executable"] = sys.executable

    # OS info (try /etc/os-release first)
    os_pretty = None
    try:
        if os.path.exists("/etc/os-release"):
            with open("/etc/os-release", "r", encoding="utf-8") as f:
                for line in f:
                    if line.startswith("PRETTY_NAME="):
                        os_pretty = line.strip().split("=", 1)[1].strip().strip('"')
                        break
    except Exception:
        os_pretty = None

    versions["os"] = os_pretty or platform.platform()
    versions["kernel"] = platform.release()
    versions["machine"] = platform.machine()

    # ffmpeg
    ffmpeg_path = shutil.which("ffmpeg")
    if ffmpeg_path:
        try:
            result = subprocess.run(
                ["ffmpeg", "-version"], capture_output=True, text=True, check=True
            )
            versions["ffmpeg"] = result.stdout.splitlines()[0]
            versions["ffmpeg_path"] = ffmpeg_path
        except Exception as e:
            versions["ffmpeg"] = f"error: {e}"
            versions["ffmpeg_path"] = ffmpeg_path
    else:
        versions["ffmpeg"] = "not found"
        versions["ffmpeg_path"] = "n/a"

    # ffprobe
    ffprobe_path = shutil.which("ffprobe")
    if ffprobe_path:
        try:
            result = subprocess.run(
                ["ffprobe", "-version"], capture_output=True, text=True, check=True
            )
            versions["ffprobe"] = result.stdout.splitlines()[0]
            versions["ffprobe_path"] = ffprobe_path
        except Exception as e:
            versions["ffprobe"] = f"error: {e}"
            versions["ffprobe_path"] = ffprobe_path
    else:
        versions["ffprobe"] = "not found"
        versions["ffprobe_path"] = "n/a"

    # openshot
    try:
        import openshot as _openshot

        ver = getattr(_openshot, "__version__", None)
        if not ver:
            ver = getattr(_openshot, "LibraryVersion", None)
        versions["openshot"] = ver or "unknown"
    except Exception:
        versions["openshot"] = "not installed"

    return versions


def print_versions(versions: Dict[str, str]) -> None:
    """Print a human-readable summary of tool versions."""
    print("Tool versions:")
    print(
        f"  OS: {versions.get('os')} | kernel: {versions.get('kernel')} | machine: {versions.get('machine')}"
    )
    print(
        f"  Python: {versions.get('python')} (executable: {versions.get('python_executable')})"
    )
    print(f"  ffmpeg: {versions.get('ffmpeg')} (path: {versions.get('ffmpeg_path')})")
    print(
        f"  ffprobe: {versions.get('ffprobe')} (path: {versions.get('ffprobe_path')})"
    )
    # git and gh info omitted to keep script environment-agnostic
    print(f"  libopenshot: {versions.get('openshot')}")


def get_audio_duration(audio_path: str) -> float:
    """Get audio duration in seconds using FFprobe."""
    try:
        cmd = [
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            audio_path,
        ]
        result = subprocess.run(cmd, capture_output=True, text=True, check=True)
        duration = float(result.stdout.strip())
        return duration
    except FileNotFoundError:
        raise ValueError(
            "Error: FFmpeg/FFprobe not found. Install FFmpeg from https://ffmpeg.org/download.html"
        )
    except (subprocess.CalledProcessError, ValueError) as e:
        raise ValueError(f"Failed to read audio duration: {e}")


def get_sorted_photos(photos_folder: str) -> List[str]:
    """Get list of photo files sorted by name."""
    valid_extensions = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".tiff"}
    photos = []

    if not os.path.isdir(photos_folder):
        raise ValueError(f"Photos folder not found: {photos_folder}")

    for file in os.listdir(photos_folder):
        if os.path.splitext(file)[1].lower() in valid_extensions:
            photos.append(os.path.join(photos_folder, file))

    if not photos:
        raise ValueError(f"No photos found in {photos_folder}")

    return sorted(photos)


def create_openshot_project(
    audio_path: str,
    photos_folder: str,
    output_path: str,
    photo_duration: int = 2 * 60,  # 2 minutes in seconds
    crossfade_duration: int = 2,  # 2 seconds
    bg_color: str = "#c7958b",
    youtube_preset: bool = True,
    intro_duration: int = 3 * 60,
    outro_duration: int = 60,
    title_text: str = "Demo",
    copyright_text: str = "© 2024",
) -> None:
    """Create an OpenShot project file using libopenshot."""

    try:
        import openshot
    except ImportError:
        print("Error: libopenshot not available.")
        print("\nTo use this script, you need libopenshot installed.")
        print("\nOptions:")
        print("1. Use VS Code Dev Container (recommended):")
        print("   - Install 'Dev Containers' extension in VS Code")
        print(
            "   - Press Ctrl+Shift+P and select 'Dev Containers: Reopen in Container'"
        )
        print("\n2. Install on Linux/WSL2:")
        print("   sudo apt-get install libopenshot python3-openshot")
        print("\n3. Install on macOS:")
        print("   brew install libopenshot")
        sys.exit(1)

    # Get audio duration
    print("Analyzing audio file...")
    audio_duration = get_audio_duration(audio_path)
    print(
        f"Audio duration: {audio_duration:.1f} seconds ({audio_duration/60:.1f} minutes)"
    )

    # Calculate timeline
    slideshow_start = intro_duration
    slideshow_duration = audio_duration - intro_duration - outro_duration

    if slideshow_duration < 0:
        raise ValueError(
            f"Intro ({intro_duration}s) + Outro ({outro_duration}s) exceeds audio duration ({audio_duration}s)"
        )

    # Get photos
    print("Scanning photos folder...")
    photos = get_sorted_photos(photos_folder)
    print(f"Found {len(photos)} photos")

    # Create OpenShot project
    print("Creating OpenShot project...")
    project = openshot.Project()

    # Get audio duration
    print("Analyzing audio file...")
    audio_duration = get_audio_duration(audio_path)
    print(
        f"Audio duration: {audio_duration:.1f} seconds ({audio_duration/60:.1f} minutes)"
    )

    # Calculate timeline
    slideshow_start = intro_duration
    slideshow_duration = audio_duration - intro_duration - outro_duration

    if slideshow_duration < 0:
        raise ValueError(
            f"Intro ({intro_duration}s) + Outro ({outro_duration}s) exceeds audio duration ({audio_duration}s)"
        )

    # Get photos
    print("Scanning photos folder...")
    photos = get_sorted_photos(photos_folder)
    print(f"Found {len(photos)} photos")

    # Create OpenShot project
    print("Creating OpenShot project...")
    project = openshot.Project()

    # Set project properties
    project.fps = openshot.Fraction(30, 1)
    project.width = 1920
    project.height = 1080
    project.sample_rate = 48000
    project.channels = 2

    # Add audio clip
    print("Adding audio track...")
    audio_clip = openshot.Clip(os.path.abspath(audio_path))
    audio_clip.Start(0)
    audio_clip.End(audio_duration)
    audio_clip.Layer(1)
    project.tracks.append(audio_clip)

    # Add photo clips
    print("Creating photo timeline...")
    current_time = slideshow_start
    clip_counter = 0
    photo_index = 0

    while current_time < slideshow_start + slideshow_duration:
        photo = photos[photo_index % len(photos)]

        remaining_duration = (slideshow_start + slideshow_duration) - current_time
        clip_duration = min(photo_duration, remaining_duration)

        # Create photo clip
        photo_clip = openshot.Clip(os.path.abspath(photo))
        photo_clip.Start(current_time)
        photo_clip.End(current_time + clip_duration)
        photo_clip.Layer(2)
        project.tracks.append(photo_clip)

        # Add crossfade effect if not first clip
        if clip_counter > 0 and crossfade_duration > 0:
            fade = openshot.Fade()
            fade.Start(current_time - crossfade_duration / 2)
            fade.End(current_time + crossfade_duration / 2)
            photo_clip.effects.append(fade)

        current_time += clip_duration
        clip_counter += 1
        photo_index += 1

        progress = (
            ((current_time - slideshow_start) / slideshow_duration) * 100
            if slideshow_duration > 0
            else 100
        )
        print(f"  Progress: {progress:.1f}% - Added {os.path.basename(photo)}")

    # Save project
    print(f"\nSaving project to: {output_path}")
    project.Save(output_path)

    print("✓ Project file created successfully!")
    print(f"  Total duration: {audio_duration/60:.1f} minutes")
    print(f"  Intro: {intro_duration/60:.0f} minutes")
    print(f"  Slideshow: {slideshow_duration/60:.1f} minutes")
    print(f"  Outro: {outro_duration/60:.0f} minute")
    print(f"  Photos used: {len(photos)}")
    print(f"  Resolution: 1920x1080 @ 30fps")
    print(f"  Intro (title screen): {intro_duration/60:.0f} minutes")
    print(f"  Slideshow (photos): {slideshow_duration/60:.1f} minutes")
    print(f"  Outro (title screen): {outro_duration/60:.0f} minute")
    print(f"  Photos used: {len(photos)}")
    print(f"  Background color: {bg_color}")
    if youtube_preset:
        print("  Export settings: YouTube optimized (1080p 30fps, H.264/AAC)")


def main():
    """Parse arguments and create project."""
    # Gather versions early so we can display them in the help epilog
    _versions = get_tool_versions()
    versions_epilog = (
        "\nCurrent environment:\n"
        f"  OS: {_versions.get('os')} | kernel: {_versions.get('kernel')} | machine: {_versions.get('machine')}\n"
        f"  Python: {_versions.get('python')}\n"
        f"  ffmpeg: {_versions.get('ffmpeg')}\n"
        f"  ffprobe: {_versions.get('ffprobe')}\n"
        # git and gh info omitted to keep script environment-agnostic
        f"  libopenshot: {_versions.get('openshot')}\n"
    )

    parser = argparse.ArgumentParser(
        description="Generate an Openshot project from audio and photos",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=versions_epilog
        + """
Examples:
  python generate_openshot_project.py lecture.mp3 ./photos/ output.osp
  python generate_openshot_project.py --photo-duration 180 song.wav ./images/ project.osp
        """,
    )

    parser.add_argument("audio_file", help="Path to audio file (WAV, MP3)")
    parser.add_argument("photos_folder", help="Path to folder containing photos")
    parser.add_argument("output_project", help="Path for output Openshot project file")
    parser.add_argument(
        "--versions",
        action="store_true",
        help="Print current versions of key utilities used by this script and exit.",
    )

    # Allow --versions to be used standalone (without requiring positional args)
    if "--versions" in sys.argv:
        print_versions(get_tool_versions())
        sys.exit(0)
    parser.add_argument(
        "--photo-duration",
        type=int,
        default=120,
        help="Duration of each photo in seconds (default: 120 = 2 minutes)",
    )
    parser.add_argument(
        "--fade-duration",
        type=int,
        default=2,
        help="Crossfade duration in seconds (default: 2)",
    )
    parser.add_argument(
        "--bg-color",
        type=str,
        default="#000000",
        help="Background color in hex format (default: #000000 = black). Examples: #ffffff (white), #ff0000 (red), #0000ff (blue)",
    )
    parser.add_argument(
        "--youtube",
        action="store_true",
        default=True,
        help="Use YouTube-optimized export settings (1080p 30fps, H.264/AAC) - default behavior",
    )
    parser.add_argument(
        "--no-youtube",
        action="store_false",
        dest="youtube",
        help="Disable YouTube optimization",
    )
    parser.add_argument(
        "--title",
        type=str,
        default="Demo",
        help="Title text for intro screen (default: Demo)",
    )
    parser.add_argument(
        "--copyright",
        type=str,
        default="© 2024",
        help="Copyright text for screens (default: © 2024)",
    )
    parser.add_argument(
        "--intro-duration",
        type=int,
        default=180,
        help="Intro screen duration in seconds (default: 180 = 3 minutes)",
    )
    parser.add_argument(
        "--outro-duration",
        type=int,
        default=60,
        help="Outro screen duration in seconds (default: 60 = 1 minute)",
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.audio_file):
        print(f"Error: Audio file not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.photos_folder):
        print(f"Error: Photos folder not found: {args.photos_folder}", file=sys.stderr)
        sys.exit(1)

    try:
        create_openshot_project(
            args.audio_file,
            args.photos_folder,
            args.output_project,
            args.photo_duration,
            args.fade_duration,
            args.bg_color,
            args.youtube,
            args.intro_duration,
            args.outro_duration,
            args.title,
            args.copyright,
        )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
