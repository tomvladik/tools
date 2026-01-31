# Windows Update & Docker Desktop Fix Scripts

This repository contains scripts for troubleshooting and resolving common issues with Windows Update, WSL, and Docker Desktop on Windows systems.

## Included Scripts


- **Fix-WU-ShowHide-Troubleshooter.ps1**  
  Downloads and launches Microsoft's official Windows Update Show/Hide Troubleshooter. Use to hide problematic updates that repeatedly fail or cause errors in Windows Update.

- **fix-WU-Visual-Studio-Client-Detector-Utility.ps1**  
  Workaround for Windows Update error 0x80070643 related to the "Visual Studio Client Detector Utility" (actually a WSL kernel update). Manually downloads and installs the WSL kernel update MSI to bypass Windows Update issues.

- **Get-WU-LogInfo.ps1**  
  Analyzes Windows Update logs, extracts error codes, and summarizes update failures. Generates a detailed report to help diagnose persistent Windows Update problems.

