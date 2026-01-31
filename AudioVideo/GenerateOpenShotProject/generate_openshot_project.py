#!/usr/bin/env python3
import sys
import os
# Add Debian dist-packages to path for python3-openshot
if '/usr/lib/python3/dist-packages' not in sys.path:
    sys.path.insert(0, '/usr/lib/python3/dist-packages')

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
import re
from pathlib import Path
from typing import List, Tuple, Dict, Any, Optional
import shutil
import platform

# Constants
DEFAULT_BG_COLOR = "#c7958b"
DEFAULT_TRIM_START = 0.0
DEFAULT_TRIM_END = 0.0


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
                        os_pretty = line.strip().split(
                            "=", 1)[1].strip().strip('"')
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

        ver = getattr(_openshot, "OPENSHOT_VERSION_FULL", None)
        if not ver:
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
    print(
        f"  ffmpeg: {versions.get('ffmpeg')} (path: {versions.get('ffmpeg_path')})")
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
        result = subprocess.run(
            cmd, capture_output=True, text=True, check=True)
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


def compute_photo_and_fade(slideshow_duration: float, num_photos: int, requested_photo: float, requested_fade: float) -> tuple:
    """Return per-photo duration and fade that ensure all photos fit the slideshow.

    If the requested durations are too long to fit, shorten the photo duration and, if needed,
    the fade to at most half the photo duration. This keeps all photos visible without exceeding
    the available slideshow time.
    """
    if num_photos <= 0:
        return requested_photo, min(requested_fade, requested_photo / 2)

    max_per_photo = slideshow_duration / num_photos if slideshow_duration > 0 else requested_photo
    photo_duration = min(requested_photo, max_per_photo) if max_per_photo > 0 else requested_photo

    # Keep fade at most half the clip so it can fit
    fade_duration = min(requested_fade, photo_duration / 2)
    return photo_duration, fade_duration


def render_video_with_libopenshot(
    audio_path: str,
    photos_folder: str,
    output_path: str,
    photo_duration: int = 120,
    fade_duration: float = 2.5,
    bg_color: str = "#000000",
    youtube_preset: bool = True,
    intro_duration: int = 180,
    outro_duration: int = 60,
    test_run: bool = False,
) -> None:
    """Render video using libopenshot Timeline and FFmpegWriter (like a video editor)."""
    
    # Test run settings
    if test_run:
        width, height, fps = 320, 200, 10
        print("🧪 TEST RUN MODE: Using draft settings (320x200@10fps)")
    else:
        width, height, fps = 1920, 1080, 30
    try:
        import openshot
    except ImportError:
        raise RuntimeError("libopenshot not installed. Install with: apt-get install python3-openshot")
    
    print("Analyzing audio file...")
    audio_duration = get_audio_duration(audio_path)
    print(f"Audio duration: {audio_duration:.1f} seconds ({audio_duration/60:.1f} minutes)")

    slideshow_start = intro_duration
    slideshow_duration = audio_duration - intro_duration - outro_duration

    if slideshow_duration < 0:
        raise ValueError(
            f"Intro ({intro_duration}s) + Outro ({outro_duration}s) exceeds audio duration ({audio_duration}s)"
        )

    print("Scanning photos folder...")
    photos = get_sorted_photos(photos_folder)
    print(f"Found {len(photos)} photos")

    effective_photo_duration, effective_fade_duration = compute_photo_and_fade(
        slideshow_duration, len(photos), photo_duration, fade_duration
    )
    if effective_photo_duration != photo_duration:
        print(f"Adjusted photo duration to {effective_photo_duration:.2f}s to fit all photos")
    if effective_fade_duration != fade_duration:
        print(f"Adjusted fade duration to {effective_fade_duration:.2f}s to fit clip length")

    # Calculate photo schedule with crossfade overlaps
    print("Planning slideshow...")
    photo_schedule = []
    current_time = slideshow_start
    photo_index = 0

    while current_time < slideshow_start + slideshow_duration:
        photo = photos[photo_index % len(photos)]
        remaining_duration = (slideshow_start + slideshow_duration) - current_time
        clip_duration = min(effective_photo_duration, remaining_duration)
        
        photo_schedule.append({
            'file': os.path.abspath(photo),
            'start': current_time,
            'duration': clip_duration
        })
        
        current_time += clip_duration
        photo_index += 1
        
        progress = (((current_time - slideshow_start) / slideshow_duration) * 100
                   if slideshow_duration > 0 else 100)
        print(f"  Progress: {progress:.1f}% - Scheduled {os.path.basename(photo)}")

    print(f"\nBuilding OpenShot Timeline...")
    
    # Create timeline with variable resolution
    timeline = openshot.Timeline(width, height, openshot.Fraction(fps, 1), 44100, 2, openshot.LAYOUT_STEREO)
    
    # Parse background color (hex to RGB)
    bg_hex = bg_color.lstrip('#')
    bg_r = int(bg_hex[0:2], 16)
    bg_g = int(bg_hex[2:4], 16)
    bg_b = int(bg_hex[4:6], 16)
    
    # Skip background layer for now - not needed if photos fill screen
    
    # Add audio clip
    print("  Adding audio track...")
    audio_clip = openshot.Clip(os.path.abspath(audio_path))
    audio_clip.Layer(1)
    audio_clip.Position(0)
    audio_clip.Start(0)
    audio_clip.End(audio_duration)
    timeline.AddClip(audio_clip)
    
    # Add photo clips with transitions
    print("  Adding photo clips...")
    for idx, item in enumerate(photo_schedule):
        photo_clip = openshot.Clip(item['file'])
        photo_clip.Layer(2 + idx)  # Each photo on its own layer for transitions
        photo_clip.Position(item['start'])
        photo_clip.Start(0)
        photo_clip.End(item['duration'])
        
        # Scale to fit
        photo_clip.scale = openshot.SCALE_FIT
        
        # Add fade in/out if there are crossfades
        if idx > 0:
            # Fade in from previous
            photo_clip.alpha = openshot.Keyframe()
            photo_clip.alpha.AddPoint(1, 0.0)  # Start transparent
            photo_clip.alpha.AddPoint(int(effective_fade_duration * 30), 1.0)  # Fade to opaque
        
        if idx < len(photo_schedule) - 1:
            # Fade out to next
            end_frame = int(item['duration'] * 30)
            start_fade_frame = int((item['duration'] - effective_fade_duration) * 30)
            if not hasattr(photo_clip, 'alpha') or photo_clip.alpha is None:
                photo_clip.alpha = openshot.Keyframe()
            photo_clip.alpha.AddPoint(start_fade_frame, 1.0)  # Start opaque
            photo_clip.alpha.AddPoint(end_frame, 0.0)  # Fade to transparent
        
        timeline.AddClip(photo_clip)
        
        progress = ((idx + 1) / len(photo_schedule)) * 100
        print(f"    Progress: {progress:.1f}% - Added {os.path.basename(item['file'])}")
    
    # Open timeline
    print("\nOpening timeline...")
    timeline.Open()
    
    # Create FFmpegWriter for output
    print("Rendering video using libopenshot...")
    writer = openshot.FFmpegWriter(output_path)
    bitrate = 3000000 if not test_run else 1000000
    writer.SetVideoOptions(True, "libx264", openshot.Fraction(fps, 1), width, height,
                          openshot.Fraction(1, 1), False, False, bitrate)
    writer.SetAudioOptions(True, "aac", 44100, 2, openshot.LAYOUT_STEREO, 192000)
    
    # Open writer
    writer.Open()
    
    # Render frames
    total_frames = int(audio_duration * 30)
    last_frame_reported = 0
    
    try:
        for frame_num in range(1, total_frames + 1):
            # Get frame from timeline (this is where it might crash)
            frame = timeline.GetFrame(frame_num)
            
            # Write frame
            writer.WriteFrame(frame)
            
            # Report progress every 100 frames
            if frame_num - last_frame_reported >= 100:
                percentage = int((frame_num / total_frames) * 100)
                print(f"  Rendering: {percentage}% (frame {frame_num}/{total_frames})", flush=True)
                last_frame_reported = frame_num
    
    except Exception as e:
        print(f"\n⚠ Warning: libopenshot rendering failed: {e}")
        print("  This is a known issue with libopenshot Timeline API stability.")
        print("  Falling back to direct FFmpeg rendering...")
        writer.Close()
        timeline.Close()
        
        # Fallback to direct FFmpeg rendering
        render_video(audio_path, photos_folder, output_path, effective_photo_duration, bg_color,
                youtube_preset, intro_duration, outro_duration, effective_fade_duration, test_run)
        return
    
    # Finalize
    print(f"  Rendering: 100% (frame {total_frames}/{total_frames})")
    writer.WriteTrailer()
    writer.Close()
    timeline.Close()
    
    print(f"\n✓ Video rendered successfully using libopenshot!")
    print(f"  Output: {output_path}")
    print(f"  Duration: {audio_duration/60:.1f} minutes")
    print(f"  Resolution: {width}x{height} @ {fps}fps")
    if test_run:
        print(f"  Mode: TEST RUN (draft quality)")
    print(f"  Photos used: {len(photo_schedule)}")


def detect_best_encoder() -> tuple:
    """Detect the best available hardware encoder."""
    # Try encoders in order of preference (quality/compatibility)
    encoders_to_try = [
        ('h264_vaapi', ['-vaapi_device', '/dev/dri/renderD128']),  # Intel/AMD
        ('h264_qsv', []),  # Intel Quick Sync
        ('h264_nvenc', []),  # NVIDIA
        ('libx264', []),  # Software fallback
    ]
    
    for encoder, extra_args in encoders_to_try:
        try:
            result = subprocess.run(
                ['ffmpeg', '-hide_banner', '-encoders'],
                capture_output=True, text=True, timeout=5
            )
            if encoder in result.stdout:
                # Test if encoder actually works
                test_cmd = ['ffmpeg', '-f', 'lavfi', '-i', 'color=c=black:s=64x64:d=0.1', '-an']
                if extra_args:
                    test_cmd.extend(extra_args)
                test_cmd.extend(['-c:v', encoder, '-f', 'null', '-'])
                test = subprocess.run(test_cmd, capture_output=True, timeout=5)
                if test.returncode == 0:
                    return encoder, extra_args
        except (subprocess.TimeoutExpired, FileNotFoundError):
            continue
    
    return 'libx264', []  # Software fallback


def run_ffmpeg_with_progress(cmd: List[str], total_duration: float, description: str = "Processing"):
    """Run FFmpeg command and display progress as percentage."""
    process = subprocess.Popen(
        cmd,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        universal_newlines=True,
        bufsize=1
    )
    
    last_frame_reported = 0
    frame_pattern = re.compile(r'frame=\s*(\d+)')
    time_pattern = re.compile(r'time=(\d+):(\d+):(\d+\.\d+)')
    fps = 30.0  # assumed fps
    total_frames = int(total_duration * fps)
    
    for line in process.stdout:
        # Parse frame count from FFmpeg output
        frame_match = frame_pattern.search(line)
        time_match = time_pattern.search(line)
        
        if frame_match:
            current_frame = int(frame_match.group(1))
            # Report every 100 frames
            if current_frame - last_frame_reported >= 100:
                if total_frames > 0:
                    percentage = min(100, int((current_frame / total_frames) * 100))
                    print(f"  {description}: {percentage}% (frame {current_frame}/{total_frames})", flush=True)
                else:
                    print(f"  {description}: frame {current_frame}", flush=True)
                last_frame_reported = current_frame
        elif time_match and total_duration > 0 and last_frame_reported == 0:
            # Fallback to time-based progress if frame info not available
            hours, minutes, seconds = time_match.groups()
            current_time = int(hours) * 3600 + int(minutes) * 60 + float(seconds)
            percentage = min(100, int((current_time / total_duration) * 100))
            if percentage % 10 == 0:
                print(f"  {description}: {percentage}%", flush=True)
    
    process.wait()
    
    if process.returncode != 0:
        raise RuntimeError(f"FFmpeg failed with exit code {process.returncode}")
    
    if total_frames > 0:
        print(f"  {description}: 100% (frame {total_frames}/{total_frames})", flush=True)
    else:
        print(f"  {description}: 100%", flush=True)


def render_video(
    audio_path: str,
    photos_folder: str,
    output_path: str,
    photo_duration: int = 2 * 60,
    bg_color: str = "#000000",
    youtube_preset: bool = True,
    intro_duration: int = 3 * 60,
    outro_duration: int = 60,
    fade_duration: float = 2.5,
    test_run: bool = False,
) -> None:
    """Render video directly using FFmpeg (bypasses buggy libopenshot Timeline API)."""
    
    # Test run settings: lower resolution, faster encoding
    if test_run:
        width, height, fps = 320, 200, 10
        encoder = 'mpeg4'  # Much faster than h264
        crf, preset = 31, 'ultrafast'
        print("🧪 TEST RUN MODE: Using draft settings (320x200@10fps, mpeg4 ultrafast)")
    else:
        width, height, fps = 1920, 1080, 30
        encoder = None  # Will be detected
        crf, preset = 23, 'medium'
    
    print("Analyzing audio file...")
    audio_duration = get_audio_duration(audio_path)
    print(f"Audio duration: {audio_duration:.1f} seconds ({audio_duration/60:.1f} minutes)")

    slideshow_start = intro_duration
    slideshow_duration = audio_duration - intro_duration - outro_duration

    if slideshow_duration < 0:
        raise ValueError(
            f"Intro ({intro_duration}s) + Outro ({outro_duration}s) exceeds audio duration ({audio_duration}s)"
        )

    print("Scanning photos folder...")
    photos = get_sorted_photos(photos_folder)
    print(f"Found {len(photos)} photos")

    # Auto-adjust durations so all photos fit
    effective_photo_duration, effective_fade_duration = compute_photo_and_fade(
        slideshow_duration, len(photos), photo_duration, fade_duration
    )
    if effective_photo_duration != photo_duration:
        print(f"Adjusted photo duration to {effective_photo_duration:.2f}s to fit all photos")
    if effective_fade_duration != fade_duration:
        print(f"Adjusted fade duration to {effective_fade_duration:.2f}s to fit clip length")

    # Calculate how many times each photo appears
    print("Planning slideshow...")
    photo_schedule = []
    current_time = slideshow_start
    photo_index = 0

    while current_time < slideshow_start + slideshow_duration:
        photo = photos[photo_index % len(photos)]
        remaining_duration = (slideshow_start + slideshow_duration) - current_time
        clip_duration = min(effective_photo_duration, remaining_duration)
        
        photo_schedule.append({
            'file': os.path.abspath(photo),
            'start': current_time,
            'duration': clip_duration
        })
        
        current_time += clip_duration
        photo_index += 1
        
        progress = (((current_time - slideshow_start) / slideshow_duration) * 100
                   if slideshow_duration > 0 else 100)
        print(f"  Progress: {progress:.1f}% - Scheduled {os.path.basename(photo)}")

    # Create temporary directory for intermediate files
    import tempfile
    temp_dir = tempfile.mkdtemp(prefix='openshot_render_')
    
    # Detect best encoder (unless test mode specifies one)
    if not test_run:
        encoder, encoder_args = detect_best_encoder()
        print(f"Using encoder: {encoder}")
    else:
        encoder_args = []
        print(f"Using encoder: {encoder}")
    
    try:
        # Step 1: Create video from photo slideshow with crossfades
        print(f"\nRendering photo slideshow with {effective_fade_duration}s crossfades...")
        photo_video = os.path.join(temp_dir, 'photos.mp4')
        
        if len(photo_schedule) == 1:
            # Single photo - no crossfade needed
            cmd = ['ffmpeg', '-y']
            if encoder_args:
                cmd.extend(encoder_args)
            cmd.extend([
                '-loop', '1',
                '-t', str(photo_schedule[0]['duration']),
                '-i', photo_schedule[0]['file'],
                '-vf', f'scale={width}:{height}:force_original_aspect_ratio=decrease,pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={bg_color}',
                '-r', str(fps),
                '-c:v', encoder,
            ])
            if encoder == 'libx264':
                cmd.extend(['-preset', preset, '-crf', str(crf)])
            elif encoder == 'mpeg4':
                cmd.extend(['-q:v', '15'])  # Quality 15 (lower=better, range 1-31)
            elif 'vaapi' in encoder:
                cmd.extend(['-qp', '23'])
            elif 'nvenc' in encoder or 'qsv' in encoder:
                cmd.extend(['-preset', 'medium', '-cq', '23'])
            cmd.extend(['-pix_fmt', 'yuv420p', photo_video])
        else:
            # Multiple photos - build complex filter with crossfades
            # Build FFmpeg command with all input files
            cmd = ['ffmpeg', '-y']
            for item in photo_schedule:
                cmd.extend(['-loop', '1', '-t', str(item['duration']), '-i', item['file']])
            
            # Build complex filter with scale, pad, and xfade
            filter_parts = []
            
            # Scale and pad each input
            for i in range(len(photo_schedule)):
                filter_parts.append(
                    f"[{i}:v]scale={width}:{height}:force_original_aspect_ratio=decrease,"
                    f"pad={width}:{height}:(ow-iw)/2:(oh-ih)/2:color={bg_color},setsar=1[v{i}]"
                )
            
            # Apply xfade transitions between consecutive videos
            # xfade offset is cumulative from the start of the output stream
            current_label = 'v0'
            cumulative_offset = 0
            for i in range(1, len(photo_schedule)):
                # Offset is when the transition should start in the output timeline
                # This is: previous clip duration(s) minus all the fade overlaps so far
                cumulative_offset += photo_schedule[i-1]['duration'] - effective_fade_duration
                next_label = f'v{i}x' if i < len(photo_schedule) - 1 else 'out'
                filter_parts.append(
                    f"[{current_label}][v{i}]xfade=transition=fade:duration={effective_fade_duration}:offset={cumulative_offset}[{next_label}]"
                )
                current_label = next_label
            
            filter_complex = ';'.join(filter_parts)
            
            cmd.extend(['-filter_complex', filter_complex, '-map', '[out]', '-r', str(fps), '-c:v', encoder])
            if encoder == 'libx264':
                cmd.extend(['-preset', preset, '-crf', str(crf)])
            elif encoder == 'mpeg4':
                cmd.extend(['-q:v', '15'])
            elif 'vaapi' in encoder:
                cmd.extend(['-qp', '23'])
            elif 'nvenc' in encoder or 'qsv' in encoder:
                cmd.extend(['-preset', 'medium', '-cq', '23'])
            cmd.extend(['-pix_fmt', 'yuv420p', photo_video])
        
        # Calculate total duration for progress tracking
        total_photo_duration = sum(p['duration'] for p in photo_schedule)
        print(f"  Total photo slideshow duration: {total_photo_duration:.1f}s")
        # Update fps for progress calculation
        old_fps = 30.0
        cmd_fps = fps
        run_ffmpeg_with_progress(cmd, total_photo_duration, "Rendering photos")
        
        # Verify created video duration
        probe_result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', photo_video],
            capture_output=True, text=True
        )
        actual_duration = float(probe_result.stdout.strip()) if probe_result.returncode == 0 else 0
        print(f"  Actual photo video duration: {actual_duration:.1f}s")
        
        # Step 2: Add silence periods if needed (intro/outro)
        video_with_timing = photo_video
        if intro_duration > 0 or outro_duration > 0:
            print(f"\nAdding intro/outro timing...")
            # Create black frames for intro/outro
            timed_video = os.path.join(temp_dir, 'timed.mp4')
            
            filter_parts = []
            if intro_duration > 0:
                filter_parts.append(f"color=c={bg_color}:s={width}x{height}:d={intro_duration}:r={fps}[intro]")
            if outro_duration > 0:
                filter_parts.append(f"color=c={bg_color}:s={width}x{height}:d={outro_duration}:r={fps}[outro]")
            
            # Build concat filter
            inputs = []
            if intro_duration > 0:
                inputs.append('[intro]')
            inputs.append('[0:v]')
            if outro_duration > 0:
                inputs.append('[outro]')
            
            concat_filter = f"{''.join(inputs)}concat=n={len(inputs)}:v=1:a=0[outv]"
            full_filter = ';'.join(filter_parts + [concat_filter]) if filter_parts else concat_filter
            
            cmd = ['ffmpeg', '-y']
            if encoder_args:
                cmd.extend(encoder_args)
            cmd.extend([
                '-i', photo_video,
                '-filter_complex', full_filter,
                '-map', '[outv]',
                '-c:v', encoder,
            ])
            if encoder == 'libx264':
                cmd.extend(['-preset', preset, '-crf', str(crf)])
            elif encoder == 'mpeg4':
                cmd.extend(['-q:v', '15'])
            elif 'vaapi' in encoder:
                cmd.extend(['-qp', '23'])
            elif 'nvenc' in encoder or 'qsv' in encoder:
                cmd.extend(['-preset', 'medium', '-cq', '23'])
            cmd.extend(['-pix_fmt', 'yuv420p', timed_video])
            
            run_ffmpeg_with_progress(cmd, audio_duration, "Adding intro/outro")
            
            video_with_timing = timed_video
        
        # Step 3: Combine with audio
        print(f"\nCombining video with audio...")
        
        # First verify intermediate video duration
        probe_result = subprocess.run(
            ['ffprobe', '-v', 'error', '-show_entries', 'format=duration', 
             '-of', 'default=noprint_wrappers=1:nokey=1', video_with_timing],
            capture_output=True, text=True
        )
        video_duration = float(probe_result.stdout.strip()) if probe_result.returncode == 0 else 0
        print(f"  Intermediate video duration: {video_duration:.1f}s")
        
        # If video is shorter than audio, loop it
        if video_duration < audio_duration - 0.1:  # Small tolerance for rounding
            print(f"  Extending video to match audio duration ({audio_duration:.1f}s)...")
            extended_video = os.path.join(temp_dir, 'extended.mp4')
            # Calculate how many loops needed
            loops_needed = int(audio_duration / video_duration) + 1
            
            # Create concat file
            concat_file = os.path.join(temp_dir, 'concat.txt')
            with open(concat_file, 'w') as f:
                for _ in range(loops_needed):
                    f.write(f"file '{video_with_timing}'\n")
            
            cmd_extend = [
                'ffmpeg', '-y',
                '-f', 'concat',
                '-safe', '0',
                '-i', concat_file,
                '-t', str(audio_duration),
                '-c', 'copy',
                extended_video
            ]
            subprocess.run(cmd_extend, capture_output=True)
            video_with_timing = extended_video
        
        cmd = [
            'ffmpeg', '-y',
            '-i', video_with_timing,
            '-i', os.path.abspath(audio_path),
            '-c:v', 'copy',
            '-c:a', 'aac',
            '-b:a', '192k',
            '-shortest',
            output_path
        ]
        
        run_ffmpeg_with_progress(cmd, audio_duration, "Merging audio")
        
        print(f"\n✓ Video rendered successfully!")
        print(f"  Output: {output_path}")
        print(f"  Duration: {audio_duration/60:.1f} minutes")
        print(f"  Resolution: {width}x{height} @ {fps}fps")
        if test_run:
            print(f"  Mode: TEST RUN (draft quality)")
        print(f"  Photos used: {len(photo_schedule)}")
        
    finally:
        # Clean up temp files
        import shutil
        shutil.rmtree(temp_dir, ignore_errors=True)


def create_openshot_project(
    audio_path: str,
    photos_folder: str,
    output_path: str,
    photo_duration: int = 2 * 60,  # 2 minutes in seconds
    crossfade_duration: int = 2,  # 2 seconds
    bg_color: str = DEFAULT_BG_COLOR,
    youtube_preset: bool = True,
    intro_duration: int = 3 * 60,
    outro_duration: int = 60,
    title_text: str = "Demo",
    copyright_text: str = "© 2024",
    trim_start: float = DEFAULT_TRIM_START,
    trim_end: float = DEFAULT_TRIM_END,
) -> None:
    """Create an OpenShot project file (.osp) as JSON."""

    # Get openshot version for metadata (optional)
    openshot_version = "unknown"
    openshot = None
    try:
        import openshot as _openshot
        openshot = _openshot
        openshot_version = getattr(openshot, "OPENSHOT_VERSION_FULL", "0.2.7")
    except ImportError:
        raise RuntimeError("libopenshot not installed. Install python3-openshot in the devcontainer.")

    # Get audio duration
    print("Analyzing audio file...")
    raw_audio_duration = get_audio_duration(audio_path)
    audio_duration = raw_audio_duration - trim_start - trim_end
    if audio_duration <= 0:
        raise ValueError(
            f"Trim values (start={trim_start}s, end={trim_end}s) exceed audio duration ({raw_audio_duration:.1f}s)"
        )
    print(
        f"Audio duration: {audio_duration:.1f} seconds ({audio_duration/60:.1f} minutes) [trimmed from {raw_audio_duration:.1f}s]"
    )

    # Calculate timeline
    slideshow_start = intro_duration
    slideshow_duration = audio_duration - intro_duration - outro_duration

    # Auto-adjust intro/outro if they exceed trimmed audio
    if slideshow_duration < 0:
        # Reduce intro/outro proportionally
        total_io = intro_duration + outro_duration
        if total_io > audio_duration * 0.8:  # If intro+outro > 80% of audio
            # Scale them down to fit 60% of audio
            scale = (audio_duration * 0.6) / total_io
            intro_duration = max(5, int(intro_duration * scale))  # Keep at least 5s
            outro_duration = max(5, int(outro_duration * scale))
            slideshow_start = intro_duration
            slideshow_duration = audio_duration - intro_duration - outro_duration
            print(f"Auto-adjusted intro to {intro_duration}s, outro to {outro_duration}s")
    
    if slideshow_duration < 0:
        raise ValueError(
            f"Intro ({intro_duration}s) + Outro ({outro_duration}s) exceeds audio duration ({audio_duration}s)"
        )

    # Get photos
    print("Scanning photos folder...")
    photos = get_sorted_photos(photos_folder)
    print(f"Found {len(photos)} photos")

    effective_photo_duration, effective_fade_duration = compute_photo_and_fade(
        slideshow_duration, len(photos), photo_duration, crossfade_duration
    )
    if effective_photo_duration != photo_duration:
        print(f"Adjusted photo duration to {effective_photo_duration:.2f}s to fit all photos")
    if effective_fade_duration != crossfade_duration:
        print(f"Adjusted transition duration to {effective_fade_duration:.2f}s to fit clip length")

    # We'll create the .osp file manually as JSON
    # (OpenShot project files are JSON, not binary)
    print("Creating OpenShot timeline...")

    # Add audio clip (placeholder - will be in JSON structure)
    print("Adding audio track...")

    # Add photo clips
    print("Creating photo timeline...")
    current_time = slideshow_start
    clip_counter = 0
    photo_index = 0

    while current_time < slideshow_start + slideshow_duration:
        photo = photos[photo_index % len(photos)]

        remaining_duration = (
            slideshow_start + slideshow_duration) - current_time
        clip_duration = min(effective_photo_duration, remaining_duration)

        # Photos will be added to JSON structure during save
        
        current_time += clip_duration
        clip_counter += 1
        photo_index += 1

        progress = (
            ((current_time - slideshow_start) / slideshow_duration) * 100
            if slideshow_duration > 0
            else 100
        )
        print(f"  Progress: {progress:.1f}% - Added {os.path.basename(photo)}")

    # Save project as JSON (OpenShot .osp format)
    print(f"\nSaving project to: {output_path}")
    
    # Create OpenShot project structure (optionally using libopenshot for clip JSON)
    # .osp files are JSON with specific structure for OpenShot
    # Keep a dedicated layer for audio and one shared layer for all photos so timeline stays tidy.
    audio_layer = 1000000
    photo_layer = 2000000

    project_data = {
        "id": str(uuid.uuid4()),
        "version": {
            "openshot-qt": "3.0.0",
            "libopenshot": openshot_version
        },
        "clips": [],
        "effects": [],
        "files": [],
        "duration": int(audio_duration),
        "scale": 15,
        "tick_pixels": 100,
        "playhead_position": 0,
        "profile": "HD 1080p 30 fps",
        "layers": [
            {"id": str(uuid.uuid4()), "number": photo_layer, "y": 0, "label": "Photos", "lock": False},
            {"id": str(uuid.uuid4()), "number": audio_layer, "y": 0, "label": "Audio", "lock": False}
        ],
        # Add explicit timing/ratio metadata expected by newer OpenShot builds
        "fps": {"num": 30, "den": 1},
        "display_ratio": {"num": 16, "den": 9},
        "pixel_ratio": {"num": 1, "den": 1},
        "sample_rate": 44100,
        "channels": 2,
        "width": 1920,
        "height": 1080,
        "markers": [],
        "progress": [],
        "history": {"undo": [], "redo": []},
        "export_path": ""
    }
    
    # Calculate relative paths from OSP file location for portability
    osp_dir = os.path.dirname(os.path.abspath(output_path))
    
    def get_portable_path(file_path):
        """Get path relative to OSP file if possible, otherwise absolute."""
        abs_path = os.path.abspath(file_path)
        try:
            rel_path = os.path.relpath(abs_path, osp_dir)
            # Only use relative path if it doesn't go up too many directories
            if not rel_path.startswith('../../../'):
                return rel_path
        except ValueError:
            # Different drives on Windows
            pass
        return abs_path
    
    def _openshot_json(obj: Any) -> Optional[Dict[str, Any]]:
        if obj is None:
            return None
        for method_name in ("Json", "json", "ToJson", "toJson"):
            if hasattr(obj, method_name):
                try:
                    raw = getattr(obj, method_name)()
                    if isinstance(raw, str):
                        return json.loads(raw)
                    if isinstance(raw, dict):
                        return raw
                except Exception:
                    return None
        return None

    def _build_clip_json_with_libopenshot(
        file_path: str,
        layer: int,
        position: float,
        start: float,
        end: float,
        scale_mode: str,
        has_audio: bool,
        has_video: bool,
        alpha_points: Optional[List[Tuple[float, float]]] = None,
    ) -> Optional[Dict[str, Any]]:
        if openshot is None:
            return None
        try:
            clip = openshot.Clip(os.path.abspath(file_path))
            clip.Layer(layer)
            clip.Position(position)
            clip.Start(start)
            clip.End(end)
            if scale_mode == "fit" and hasattr(openshot, "SCALE_FIT"):
                clip.scale = openshot.SCALE_FIT
            elif scale_mode == "crop" and hasattr(openshot, "SCALE_CROP"):
                clip.scale = openshot.SCALE_CROP
            if alpha_points:
                kf = openshot.Keyframe()
                for frame, value in alpha_points:
                    kf.AddPoint(frame, value)
                clip.alpha = kf
            data = _openshot_json(clip)
            if not data:
                return None
            # normalize booleans / flags
            if "enabled" not in data:
                data["enabled"] = True
            # Always set has_audio / has_video so timeline logic is explicit
            data["has_audio"] = {
                "Points": [{"co": {"X": 1, "Y": 1 if has_audio else 0}, "interpolation": 0}]
            }
            data["has_video"] = {
                "Points": [{"co": {"X": 1, "Y": 1 if has_video else 0}, "interpolation": 0}]
            }
            # Fix reader path to be relative (API embeds absolute path)
            if "reader" in data and "path" in data["reader"]:
                data["reader"]["path"] = get_portable_path(file_path)
            return data
        except Exception:
            return None

    # Add audio file
    audio_file_data = {
        "id": str(uuid.uuid4()),
        "path": get_portable_path(audio_path),
        "media_type": "audio",
        "reader": {
            "type": "FFmpegReader",
            "path": get_portable_path(audio_path),
            "has_audio": True,
            "has_video": False,
            "sample_rate": 44100,
            "channels": 2,
            "channel_layout": 3,
            "fps": {"num": 30, "den": 1},
            "display_ratio": {"num": 16, "den": 9},
            "pixel_ratio": {"num": 1, "den": 1}
        }
    }
    project_data["files"].append(audio_file_data)
    
    # Add audio clip
    audio_clip_data = {
        "id": str(uuid.uuid4()),
        "file_id": audio_file_data["id"],
        "title": os.path.basename(audio_path),
        "layer": audio_layer,
        "position": 0.0,
        "start": trim_start,
        "end": trim_start + audio_duration,
        "duration": audio_duration,
        "alpha": {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": 0}]},
        "scale": 1,
        "scale_x": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": 0}]},
        "scale_y": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": 0}]},
        "anchor": 0,
        "enabled": True,
        "has_audio": {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": 0}]},
        "has_video": {"Points": [{"co": {"X": 1, "Y": 0}, "interpolation": 0}]}
    }
    audio_clip_json = _build_clip_json_with_libopenshot(
        audio_path,
        audio_layer,
        0.0,
        trim_start,
        trim_start + audio_duration,
        "crop",
        has_audio=True,
        has_video=False,
        alpha_points=None,
    )
    if audio_clip_json:
        audio_clip_json.update(
            {
                "id": audio_clip_data["id"],
                "file_id": audio_file_data["id"],
                "title": os.path.basename(audio_path),
            }
        )
        audio_clip_data = audio_clip_json
    project_data["clips"].append(audio_clip_data)
    
    # Calculate photo schedule with overlaps for crossfades
    photo_clips = []
    current_time = slideshow_start
    photo_index = 0
    
    while current_time < slideshow_start + slideshow_duration:
        photo = photos[photo_index % len(photos)]
        remaining_duration = (slideshow_start + slideshow_duration) - current_time
        clip_duration = min(effective_photo_duration, remaining_duration)
        
        photo_clips.append({
            'photo': photo,
            'position': current_time,
            'duration': clip_duration,
            'index': photo_index
        })
        
        current_time += clip_duration
        photo_index += 1
    
    # Add photo files and clips with proper positioning for crossfades
    clip_objects = []
    for idx, item in enumerate(photo_clips):
        photo = item['photo']
        
        photo_file_data = {
            "id": str(uuid.uuid4()),
            "path": get_portable_path(photo),
            "media_type": "image",
            "reader": {
                "type": "QtImageReader",
                "path": get_portable_path(photo),
                "has_audio": False,
                "has_video": True,
                "width": 1920,
                "height": 1080,
                "fps": {"num": 30, "den": 1},
                "display_ratio": {"num": 16, "den": 9},
                "pixel_ratio": {"num": 1, "den": 1}
            }
        }
        project_data["files"].append(photo_file_data)
        
        # For crossfades, clips need to overlap
        # Extend clip duration to include crossfade with next clip
        clip_duration = item['duration']
        if idx < len(photo_clips) - 1:
            # Extend to overlap with next clip
            clip_duration += effective_fade_duration
        
        photo_clip_data = {
            "id": str(uuid.uuid4()),
            "file_id": photo_file_data["id"],
            "title": os.path.basename(photo),
            "layer": photo_layer,
            "position": item['position'],
            "start": 0.0,
            "end": clip_duration,
            "duration": clip_duration,
            "alpha": {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": 0}]},
            "scale": 1,
            "scale_x": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": 0}]},
            "scale_y": {"Points": [{"co": {"X": 1, "Y": 1.0}, "interpolation": 0}]},
            "anchor": 0,
            "enabled": True,
            "has_audio": {"Points": [{"co": {"X": 1, "Y": 0}, "interpolation": 0}]},
            "has_video": {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": 0}]}
        }
        # Alpha fade keyframes disabled when using Mask transitions
        # (Mask handles the fade; alpha keyframes would conflict)
        alpha_points = None

        photo_clip_json = _build_clip_json_with_libopenshot(
            photo,
            photo_layer,
            item["position"],
            0.0,
            clip_duration,
            "fit",
            has_audio=False,
            has_video=True,
            alpha_points=alpha_points,
        )
        if photo_clip_json:
            photo_clip_json.update(
                {
                    "id": photo_clip_data["id"],
                    "file_id": photo_file_data["id"],
                    "title": os.path.basename(photo),
                }
            )
            photo_clip_data = photo_clip_json
        project_data["clips"].append(photo_clip_data)
        clip_objects.append(photo_clip_data)
    
    # Add fade transitions between consecutive photos
    for idx in range(len(clip_objects) - 1):
        current_clip = clip_objects[idx]
        next_clip = clip_objects[idx + 1]
        
        # Transition occurs during the overlap period
        # Position: where next clip starts (which is overlap region start)
        transition_position = photo_clips[idx + 1]['position']
        
        transition_data = {
            "id": str(uuid.uuid4()),
            "layer": photo_layer,
            "position": transition_position,
            "start": 0.0,
            "end": effective_fade_duration,
            "duration": effective_fade_duration,
            "type": "Mask",
            "brightness": {"Points": [{"co": {"X": 1, "Y": 1}, "interpolation": 0}]},
            "contrast": {"Points": [{"co": {"X": 1, "Y": 3}, "interpolation": 0}]},
            "reader": {
                "type": "QtImageReader",
                "path": "@transitions/common/fade.svg"
            },
            "replace_image": False
        }
        project_data["effects"].append(transition_data)
    
    # Mirror timeline data for OpenShot 3.x compatibility
    project_data["timeline"] = {
        "clips": project_data["clips"],
        "effects": project_data["effects"],
        "duration": project_data["duration"],
        "scale": project_data["scale"],
        "tick_pixels": project_data["tick_pixels"],
        "playhead_position": project_data["playhead_position"],
        "profile": project_data["profile"],
        "layers": project_data["layers"],
        "fps": project_data["fps"],
        "display_ratio": project_data["display_ratio"],
        "pixel_ratio": project_data["pixel_ratio"],
        "sample_rate": project_data["sample_rate"],
        "channels": project_data["channels"],
        "width": project_data["width"],
        "height": project_data["height"]
    }

    # Write to file
    with open(output_path, 'w') as f:
        json.dump(project_data, f, indent=2)

    print("✓ Project file created successfully!")
    print(f"  Total duration: {audio_duration/60:.1f} minutes")
    print(f"  Slideshow: {slideshow_duration/60:.1f} minutes")
    print(f"  Photos used: {len(photo_clips)}")
    print(f"  Transitions: {len(photo_clips) - 1} crossfades ({effective_fade_duration}s each)")
    print(f"  Resolution: 1920x1080 @ 30fps")
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
  # Create OpenShot project file (.osp)
  python generate_openshot_project.py lecture.mp3 ./photos/ output.osp
  
  # Render video directly (produces final MP4)
  python generate_openshot_project.py --export-video lecture.mp3 ./photos/ output.mp4
  
  # Custom photo duration
  python generate_openshot_project.py --export-video --photo-duration 60 song.wav ./images/ video.mp4
        """,
    )

    parser.add_argument("audio_file", help="Path to audio file (WAV, MP3)")
    parser.add_argument(
        "photos_folder", help="Path to folder containing photos")
    parser.add_argument(
        "output_project", help="Path for output file (.osp for project, .mp4/.mkv for video)")
    parser.add_argument(
        "--versions",
        action="store_true",
        help="Print current versions of key utilities used by this script and exit.",
    )
    parser.add_argument(
        "--export-video",
        action="store_true",
        help="Render video directly instead of creating .osp project file (slower but produces final MP4)",
    )
    parser.add_argument(
        "--save-osp",
        action="store_true",
        help="Also save .osp project file when using --export-video (creates .osp alongside video)",
    )
    parser.add_argument(
        "--use-libopenshot",
        action="store_true",
        help="Use libopenshot Timeline for rendering (like a video editor). Warning: may be unstable. Only works with --export-video",
    )
    parser.add_argument(
        "--test-run",
        action="store_true",
        help="Fast draft mode: render at 640x360@15fps with ultrafast preset for quick testing. Only works with --export-video",
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
        type=float,
        default=2.5,
        help="Crossfade transition duration in seconds (default: 2.5, applies to --export-video)",
    )
    parser.add_argument(
        "--bg-color",
        type=str,
        default=DEFAULT_BG_COLOR,
        help=f"Background color in hex format (default: {DEFAULT_BG_COLOR}). Examples: #ffffff (white), #ff0000 (red), #0000ff (blue)",
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
    parser.add_argument(
        "--trim-start",
        type=float,
        default=DEFAULT_TRIM_START,
        help=f"Trim audio from the beginning in seconds (default: {DEFAULT_TRIM_START})",
    )
    parser.add_argument(
        "--trim-end",
        type=float,
        default=DEFAULT_TRIM_END,
        help=f"Trim audio from the end in seconds (default: {DEFAULT_TRIM_END})",
    )

    args = parser.parse_args()

    # Validate inputs
    if not os.path.exists(args.audio_file):
        print(
            f"Error: Audio file not found: {args.audio_file}", file=sys.stderr)
        sys.exit(1)

    if not os.path.isdir(args.photos_folder):
        print(
            f"Error: Photos folder not found: {args.photos_folder}", file=sys.stderr)
        sys.exit(1)

    try:
        if args.export_video:
            # Optionally create OSP file first
            if args.save_osp:
                osp_path = os.path.splitext(args.output_project)[0] + '.osp'
                print(f"Creating OpenShot project file: {osp_path}")
                create_openshot_project(
                    args.audio_file,
                    args.photos_folder,
                    osp_path,
                    args.photo_duration,
                    args.fade_duration,
                    args.bg_color,
                    args.youtube,
                    args.intro_duration,
                    args.outro_duration,
                    args.title,
                    args.copyright,
                    args.trim_start,
                    args.trim_end,
                )
                print()
            
            # Render video directly
            if args.use_libopenshot:
                # Use libopenshot Timeline rendering (like a video editor)
                render_video_with_libopenshot(
                    args.audio_file,
                    args.photos_folder,
                    args.output_project,
                    args.photo_duration,
                    args.fade_duration,
                    args.bg_color,
                    args.youtube,
                    args.intro_duration,
                    args.outro_duration,
                    args.test_run,
                )
            else:
                # Use direct FFmpeg rendering (more stable)
                render_video(
                    args.audio_file,
                    args.photos_folder,
                    args.output_project,
                    args.photo_duration,
                    args.bg_color,
                    args.youtube,
                    args.intro_duration,
                    args.outro_duration,
                    args.fade_duration,
                    args.test_run,
                )
        else:
            # Create .osp project file
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
                args.trim_start,
                args.trim_end,
            )
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()
