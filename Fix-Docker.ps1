<#
Fix-Docker.ps1
Maximum refresh for Docker Desktop + WSL on Windows.
Run in elevated PowerShell (Administrator).
#>

$ErrorActionPreference = "Stop"

function Assert-Admin {
    $isAdmin = ([Security.Principal.WindowsPrincipal] [Security.Principal.WindowsIdentity]::GetCurrent()).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
    if (-not $isAdmin) {
        Write-Host "This script must be run as Administrator." -ForegroundColor Red
        exit 1
    }
}

function Stop-DockerProcesses {
    Write-Host "Stopping Docker processes..." -ForegroundColor Cyan
    Get-Process | Where-Object { $_.ProcessName -match "docker" } | Stop-Process -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "com.docker.backend" -Force -ErrorAction SilentlyContinue
    Stop-Process -Name "Docker Desktop" -Force -ErrorAction SilentlyContinue
}

function Reset-WslDockerDistros {
    Write-Host "Shutting down WSL..." -ForegroundColor Cyan
    wsl --shutdown
    Start-Sleep -Seconds 3

    Write-Host "Unregistering docker-desktop distros (if present)..." -ForegroundColor Cyan
    wsl --unregister docker-desktop 2>$null
    wsl --unregister docker-desktop-data 2>$null
}

function Restart-VirtualizationServices {
    Write-Host "Restarting virtualization services..." -ForegroundColor Cyan
    Restart-Service -Name "vmcompute" -Force
    Restart-Service -Name "wslservice" -Force -ErrorAction SilentlyContinue
}

function Update-WslKernel {
    Write-Host "Updating WSL kernel..." -ForegroundColor Cyan
    try {
        wsl --update
    }
    catch {
        Write-Host "WSL update failed (error 0x80070643 is common). Trying alternative method..." -ForegroundColor Yellow
        # Download and install manually
        $wslUpdateUrl = "https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi"
        $wslMsi = "$env:TEMP\wsl_update_x64.msi"
        
        Write-Host "Downloading WSL2 kernel update..." -ForegroundColor Cyan
        Invoke-WebRequest -Uri $wslUpdateUrl -OutFile $wslMsi -UseBasicParsing
        
        Write-Host "Installing WSL2 kernel..." -ForegroundColor Cyan
        Start-Process msiexec.exe -ArgumentList "/i `"$wslMsi`" /quiet /norestart" -Wait
        
        Remove-Item $wslMsi -Force -ErrorAction SilentlyContinue
    }
}

function Remove-DockerDataDirs {
    Write-Host "Removing Docker data directories..." -ForegroundColor Cyan
    Remove-Item "$env:LOCALAPPDATA\Docker" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "$env:APPDATA\Docker" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "$env:APPDATA\Docker Desktop" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "C:\ProgramData\DockerDesktop" -Recurse -Force -ErrorAction SilentlyContinue
    Remove-Item "C:\ProgramData\Docker" -Recurse -Force -ErrorAction SilentlyContinue
}

function Repair-WindowsFeatures {
    Write-Host "Refreshing Windows virtualization features..." -ForegroundColor Cyan
    Disable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
    Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
    Disable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -NoRestart -ErrorAction SilentlyContinue

    Enable-WindowsOptionalFeature -Online -FeatureName VirtualMachinePlatform -NoRestart
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Windows-Subsystem-Linux -NoRestart
    Enable-WindowsOptionalFeature -Online -FeatureName Microsoft-Hyper-V -NoRestart -ErrorAction SilentlyContinue
}

function Repair-SystemFiles {
    Write-Host "Running DISM and SFC (can take several minutes)..." -ForegroundColor Cyan
    DISM /Online /Cleanup-Image /RestoreHealth
    sfc /scannow
}

function Fix-WindowsInstaller {
    Write-Host "Resetting Windows Installer service (fixes 0x80070643)..." -ForegroundColor Cyan
    net stop msiserver
    Start-Sleep -Seconds 2
    net start msiserver
    
    # Clear Windows Update cache
    net stop wuauserv
    Remove-Item "$env:SystemRoot\SoftwareDistribution\Download\*" -Recurse -Force -ErrorAction SilentlyContinue
    net start wuauserv
}

Assert-Admin

Write-Host "=== Docker + WSL Maximum Refresh ===" -ForegroundColor Green

Stop-DockerProcesses
Reset-WslDockerDistros

# Fix Windows Installer first (addresses 0x80070643 error)
Fix-WindowsInstaller

Restart-VirtualizationServices
Update-WslKernel
Remove-DockerDataDirs
Repair-WindowsFeatures

$runRepair = Read-Host "Run DISM + SFC system repair? (y/n)"
if ($runRepair -match "^(y|yes)$") {
    Repair-SystemFiles
}

Write-Host "Done. After restart, launch Docker Desktop to recreate WSL distros." -ForegroundColor Yellow
Write-Host ""
$restart = Read-Host "Restart Windows by FORCE now? (y/n)"
if ($restart -match "^(y|yes)$") {
    Write-Host "Restarting in 10 seconds..." -ForegroundColor Yellow
    Start-Sleep -Seconds 3
    Restart-Computer -Force
}
else {
    Write-Host "Please restart manually when ready." -ForegroundColor Yellow
}