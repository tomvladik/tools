#!/usr/bin/env python3
"""
generate_test_data.py

Create a short WAV audio file and a set of BMP photos for quick testing.

Usage:
    python make_test_data.py --out-dir ./test_data --photos 5 --duration 20

No external dependencies required (uses only Python stdlib).
"""

import argparse
import os
import math
import struct
import wave
from typing import Tuple


def parse_hex_color(s: str) -> Tuple[int, int, int]:
    s = s.lstrip("#")
    if len(s) == 3:
        s = ''.join([c*2 for c in s])
    if len(s) != 6:
        raise ValueError("Color must be in hex format like '#ff0000' or 'f00'")
    r = int(s[0:2], 16)
    g = int(s[2:4], 16)
    b = int(s[4:6], 16)
    return r, g, b


def generate_wav_8bit_melody(path: str, duration: float = 5.0, sample_rate: int = 44100, volume: float = 0.4):
    """Generate 8-bit chiptune melody.
    
    Uses square wave synthesis typical of ZX Spectrum beeper sound.
    """
    # Manic Miner melody notes (simplified version of "In the Hall of the Mountain King")
    # Note frequencies in Hz (approximate)
    notes = {
        'C4': 261.63, 'D4': 293.66, 'E4': 329.63, 'F4': 349.23,
        'G4': 392.00, 'A4': 440.00, 'B4': 493.88,
        'C5': 523.25, 'D5': 587.33, 'E5': 659.25, 'F5': 698.46,
        'G5': 783.99, 'A5': 880.00,
        'REST': 0
    }
    
    # Simplified melody sequence (repeating pattern)
    melody = [
        ('E4', 0.2), ('D4', 0.2), ('C4', 0.2), ('D4', 0.2), ('E4', 0.2), ('D4', 0.2),
        ('E4', 0.2), ('F4', 0.2), ('G4', 0.4),
        ('E4', 0.2), ('D4', 0.2), ('C4', 0.2), ('D4', 0.2), ('E4', 0.2), ('D4', 0.2),
        ('E4', 0.2), ('F4', 0.2), ('G4', 0.4),
        ('G4', 0.2), ('A4', 0.2), ('B4', 0.2), ('C5', 0.2), ('B4', 0.2), ('A4', 0.2),
        ('G4', 0.2), ('A4', 0.2), ('B4', 0.4),
        ('REST', 0.2),
    ]
    
    nframes = int(sample_rate * duration)
    n_channels = 2
    sampwidth = 2
    max_ampl = int((2 ** (sampwidth * 8 - 1)) - 1)
    
    with wave.open(path, "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)
        
        current_time = 0.0
        frame_idx = 0
        melody_idx = 0
        
        last_pct = -1
        
        while frame_idx < nframes:
            # Get current note and duration
            if melody_idx < len(melody):
                note_name, note_duration = melody[melody_idx]
                freq = notes[note_name]
            else:
                # Loop the melody
                melody_idx = 0
                note_name, note_duration = melody[melody_idx]
                freq = notes[note_name]
            
            # Calculate frames for this note
            note_frames = int(sample_rate * note_duration)
            note_end_frame = min(frame_idx + note_frames, nframes)
            
            # Generate square wave for this note
            buf = bytearray()
            for i in range(frame_idx, note_end_frame):
                t = i / sample_rate
                
                if freq == 0:  # Rest
                    sample_val = 0
                else:
                    # Square wave: alternates between +max and -max
                    phase = (t * freq) % 1.0
                    sample_val = int(volume * max_ampl if phase < 0.5 else -volume * max_ampl)
                
                # Stereo
                buf.extend(struct.pack('<h', sample_val))
                buf.extend(struct.pack('<h', sample_val))
            
            wf.writeframes(bytes(buf))
            frame_idx = note_end_frame
            current_time += note_duration
            melody_idx += 1
            
            # Progress
            pct = int((frame_idx / nframes) * 100)
            if pct - last_pct >= 10 or frame_idx >= nframes:
                print(f"  Audio generation: {pct}%")
                last_pct = pct


def generate_wav(path: str, duration: float = 5.0, sample_rate: int = 44100, freq: float = 440.0, volume: float = 0.5):
    """Generate a simple stereo WAV file with a sine tone using buffered block writes.

    This implementation writes frames in chunks to avoid slow per-frame I/O and
    prints lightweight progress so the user sees activity for long files.
    """
    nframes = int(sample_rate * duration)
    n_channels = 2
    sampwidth = 2  # bytes per sample (16-bit)

    max_ampl = int((2 ** (sampwidth * 8 - 1)) - 1)

    # Number of frames per write chunk; tuned for throughput without large memory use
    frames_per_chunk = 8192

    with wave.open(path, "wb") as wf:
        wf.setnchannels(n_channels)
        wf.setsampwidth(sampwidth)
        wf.setframerate(sample_rate)

        last_pct = -1
        for start in range(0, nframes, frames_per_chunk):
            end = min(nframes, start + frames_per_chunk)
            buf = bytearray()

            for i in range(start, end):
                t = i / sample_rate
                sample_val = int(
                    volume * math.sin(2 * math.pi * freq * t) * max_ampl)
                # stereo: duplicate samples (little-endian 16-bit)
                buf.extend(struct.pack('<h', sample_val))
                buf.extend(struct.pack('<h', sample_val))

            wf.writeframes(bytes(buf))

            # Print progress roughly every 10% or when complete
            if nframes > 0:
                pct = int((end / nframes) * 100)
                if pct - last_pct >= 10 or end == nframes:
                    print(f"  Audio generation: {pct}%")
                    last_pct = pct


def write_bmp(path: str, width: int, height: int, color: Tuple[int, int, int]):
    """Write a simple 24-bit uncompressed BMP with a solid color.

    BMP format uses little-endian headers and BGR pixel order, rows are bottom-up
    and each row is padded to a 4-byte boundary.
    """
    r, g, b = color
    row_bytes = width * 3
    padding = (4 - (row_bytes % 4)) % 4
    image_size = (row_bytes + padding) * height
    file_size = 54 + image_size

    # File header
    bfType = b'BM'
    bfSize = struct.pack('<I', file_size)
    bfReserved = struct.pack('<HH', 0, 0)
    bfOffBits = struct.pack('<I', 54)

    # DIB header (BITMAPINFOHEADER)
    biSize = struct.pack('<I', 40)
    biWidth = struct.pack('<i', width)
    biHeight = struct.pack('<i', height)
    biPlanes = struct.pack('<H', 1)
    biBitCount = struct.pack('<H', 24)
    biCompression = struct.pack('<I', 0)
    biSizeImage = struct.pack('<I', image_size)
    biXPelsPerMeter = struct.pack('<i', 0)
    biYPelsPerMeter = struct.pack('<i', 0)
    biClrUsed = struct.pack('<I', 0)
    biClrImportant = struct.pack('<I', 0)

    with open(path, 'wb') as f:
        f.write(bfType)
        f.write(bfSize)
        f.write(bfReserved)
        f.write(bfOffBits)

        f.write(biSize)
        f.write(biWidth)
        f.write(biHeight)
        f.write(biPlanes)
        f.write(biBitCount)
        f.write(biCompression)
        f.write(biSizeImage)
        f.write(biXPelsPerMeter)
        f.write(biYPelsPerMeter)
        f.write(biClrUsed)
        f.write(biClrImportant)

        row = bytes([b, g, r]) * width + (b'\x00' * padding)
        # write rows bottom-up
        for _ in range(height):
            f.write(row)


def generate_photos(folder: str, count: int = 5, width: int = 1280, height: int = 720, base_color: str = "#808080"):
    os.makedirs(folder, exist_ok=True)
    base_r, base_g, base_b = parse_hex_color(base_color)

    # Try to use Pillow for centered numbers; if not available we'll fall back to plain BMPs
    try:
        from PIL import Image, ImageDraw, ImageFont  # type: ignore
        PIL_AVAILABLE = True
    except Exception:
        PIL_AVAILABLE = False

    if PIL_AVAILABLE:
        # find a system TTF to use for better rendering
        import glob

        def find_ttf():
            candidates = glob.glob('/usr/share/fonts/**/*.ttf', recursive=True)
            candidates += glob.glob('/usr/local/share/fonts/**/*.ttf',
                                    recursive=True)
            candidates += glob.glob(os.path.expanduser(
                '~/.local/share/fonts/**/*.ttf'), recursive=True)
            return candidates[0] if candidates else None

        font_path = find_ttf()

    for i in range(count):
        # vary color across HLS space for more intensive, linear changes
        # This interpolates hue and increases saturation across the series
        import colorsys

        # normalize base RGB to [0,1]
        br = base_r / 255.0
        bg = base_g / 255.0
        bb = base_b / 255.0
        h, l, s = colorsys.rgb_to_hls(br, bg, bb)

        # position in range [0,1]
        t = i / max(1, count - 1)
        # hue will shift across +/- hue_span (fraction of full circle)
        hue_span = 0.4  # ~144 degrees total span
        new_h = (h + (t - 0.5) * hue_span) % 1.0

        # increase saturation linearly toward 1.0 for stronger colors
        new_s = min(1.0, s + (t * (1.0 - s) * 1.25))

        # slightly adjust lightness to keep colors vivid but not blown out
        # push mid items slightly lighter and extremes slightly darker
        new_l = min(1.0, max(0.0, l * (0.9 + 0.2 * (0.5 - abs(t - 0.5)))))

        nr, ng, nb = colorsys.hls_to_rgb(new_h, new_l, new_s)
        r = max(0, min(255, int(round(nr * 255))))
        g = max(0, min(255, int(round(ng * 255))))
        b = max(0, min(255, int(round(nb * 255))))

        filename = os.path.join(folder, f"photo_{i+1:03d}.bmp")

        if PIL_AVAILABLE:
            # create image and draw centered number
            img = Image.new('RGB', (width, height), (r, g, b))
            draw = ImageDraw.Draw(img)

            # choose font size large enough to be prominent
            font_size = int(min(width, height) * 0.45)
            try:
                if font_path:
                    font = ImageFont.truetype(font_path, font_size)
                else:
                    font = ImageFont.load_default()
            except Exception:
                font = ImageFont.load_default()

            text = str(i + 1)

            # robust text measurement supporting multiple Pillow versions
            def measure_text(draw_obj, txt, font_obj):
                # Prefer textbbox (accurate and modern)
                if hasattr(draw_obj, 'textbbox'):
                    try:
                        bbox = draw_obj.textbbox((0, 0), txt, font=font_obj)
                        return bbox[2] - bbox[0], bbox[3] - bbox[1]
                    except Exception:
                        pass
                # Older Pillow: textsize
                if hasattr(draw_obj, 'textsize'):
                    try:
                        return draw_obj.textsize(txt, font=font_obj)
                    except Exception:
                        pass
                # Fallback to font methods
                if hasattr(font_obj, 'getbbox'):
                    try:
                        bbox = font_obj.getbbox(txt)
                        return bbox[2] - bbox[0], bbox[3] - bbox[1]
                    except Exception:
                        pass
                if hasattr(font_obj, 'getsize'):
                    try:
                        return font_obj.getsize(txt)
                    except Exception:
                        pass
                # Last resort: estimate using font size
                return int(len(txt) * (font_size * 0.6)), font_size

            # measure text and scale down if too big
            text_w, text_h = measure_text(draw, text, font)
            if text_w > width * 0.9:
                # scale font down proportionally
                scale = (width * 0.9) / text_w
                try:
                    font = ImageFont.truetype(font_path, max(10, int(font_size * scale))) if font_path else ImageFont.load_default()
                except Exception:
                    font = ImageFont.load_default()
                text_w, text_h = measure_text(draw, text, font)

            x = (width - text_w) / 2
            y = (height - text_h) / 2

            # choose contrasting color (white or black)
            luminance = 0.299 * r + 0.587 * g + 0.114 * b
            text_fill = (0, 0, 0) if luminance > 128 else (255, 255, 255)
            stroke_fill = (255, 255, 255) if text_fill == (
                0, 0, 0) else (0, 0, 0)

            # draw with stroke for readability
            try:
                draw.text((x, y), text, font=font, fill=text_fill, stroke_width=int(
                    font_size * 0.06), stroke_fill=stroke_fill)
            except TypeError:
                # older Pillow may not support stroke_width; draw outline manually
                outline_width = max(1, int(font_size * 0.06))
                for ox in range(-outline_width, outline_width + 1):
                    for oy in range(-outline_width, outline_width + 1):
                        if ox == 0 and oy == 0:
                            continue
                        draw.text((x + ox, y + oy), text,
                                  font=font, fill=stroke_fill)
                draw.text((x, y), text, font=font, fill=text_fill)

            img.save(filename, format='BMP')

        else:
            # Pillow not available; fall back to solid BMP and advise the user
            write_bmp(filename, width, height, (r, g, b))

    if not PIL_AVAILABLE:
        print("Note: Pillow not installed; photos are solid colors without numbers. Install Pillow (pip install pillow) for numbered images.")


def main():
    parser = argparse.ArgumentParser(
        description="Generate short test audio and photo files")
    parser.add_argument("--out-dir", default="./test_data",
                        help="Output directory")
    parser.add_argument("--photos", type=int, default=5,
                        help="Number of photos to generate")
    parser.add_argument("--img-width", type=int,
                        default=1280, help="Image width")
    parser.add_argument("--img-height", type=int,
                        default=720, help="Image height")
    parser.add_argument("--duration", type=float,
                        default=300.0, help="Audio duration in seconds")
    parser.add_argument("--freq", type=float, default=440.0,
                        help="Tone frequency in Hz")
    parser.add_argument("--color", type=str, default="#808080",
                        help="Base hex color for photos, e.g. #ff0000")

    args = parser.parse_args()

    out_dir = os.path.abspath(args.out_dir)
    os.makedirs(out_dir, exist_ok=True)

    audio_path = os.path.join(out_dir, "test_audio.wav")
    photos_dir = os.path.join(out_dir, "photos")

    print("Generating audio...")
    generate_wav_8bit_melody(audio_path, duration=args.duration)

    print("Generating photos...")
    generate_photos(photos_dir, count=args.photos, width=args.img_width,
                    height=args.img_height, base_color=args.color)

    print("\nDone. Files created:")
    print(f"  Audio: {audio_path}")
    print(f"  Photos folder: {photos_dir}")
    print("\nExample usage with your existing script:")
    print(
        f"  python generate_openshot_project.py {audio_path} {photos_dir} output.osp")


if __name__ == '__main__':
    main()
