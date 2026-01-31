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

