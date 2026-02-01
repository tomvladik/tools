This repository contains scripts which I sometime need to use.
## Included Scripts
### Windows-Rectification
Scripts related toWindows Update, WSL, and Docker Desktop are in the `Windows-Rectification` folder:
- **Fix-WU-ShowHide-Troubleshooter.ps1**  
  Downloads and launches Microsoft's official Windows Update Show/Hide Troubleshooter. Use to hide problematic updates that repeatedly fail or cause errors in Windows Update.
- **fix-WU-Visual-Studio-Client-Detector-Utility.ps1**  
  Workaround for Windows Update error 0x80070643 related to the "Visual Studio Client Detector Utility" (actually a WSL kernel update). Manually downloads and installs the WSL kernel update MSI to bypass Windows Update issues.
- **Get-WU-LogInfo.ps1**  
  Analyzes Windows Update logs, extracts error codes, and summarizes update failures. Generates a detailed report to help diagnose persistent Windows Update problems.
- **Fix-Docker.ps1**  
  Performs a maximum refresh of Docker Desktop and WSL on Windows. Stops Docker processes, resets WSL distros, repairs Windows Installer, restarts virtualization services, updates the WSL kernel, removes Docker data directories, and refreshes Windows virtualization features. Optionally runs DISM and SFC system repair. Run in elevated PowerShell (Administrator).
### AudioVideo/GenerateOpenShotProject
Tools to create OpenShot projects or render videos from an audio file and a folder of photos.
- **generate_openshot_project.py**  
  Generates an OpenShot project (.osp) or renders a final video (MP4) from an audio file and a folder of photos. Features include automatic per-photo duration adjustment to match audio, crossfade transitions, intro/outro screens, background color, and two rendering modes (libopenshot Timeline or direct FFmpeg rendering with a stable fallback).

  Usage:

  ```bash
  python AudioVideo/GenerateOpenShotProject/generate_openshot_project.py [options] <audio_file> <photos_folder> <output_project>
  ```

  Requirements: ffmpeg / ffprobe (required for rendering), and optionally python3-openshot to use libopenshot Timeline rendering. See AudioVideo/GenerateOpenShotProject/README.md for full details.

- **make_test_data.py**  
  Create a short WAV audio file and a set of test photos for quick testing of the slideshow pipeline. Produces an audio file (`test_audio.wav`) and a `photos/` folder with BMP images by default; installing `Pillow` yields numbered images.

  Example:

  ```bash
  python AudioVideo/GenerateOpenShotProject/make_test_data.py --out-dir ./test_data --photos 5 --duration 20
  ```

  Notes: basic output requires only the Python standard library; installing Pillow (see AudioVideo/GenerateOpenShotProject/requirements.txt) yields nicer numbered images.

```

