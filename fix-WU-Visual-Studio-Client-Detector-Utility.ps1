<#
    FIX: Windows Update Error 0x80070643
    
    ISSUE: "Visual Studio Client Detector Utility - Install error 0x80070643"
    This error occurs when running "wsl --update" via Windows Update/Microsoft Store.
    
    ROOT CAUSE:
    - Windows Installer (msiserver) service is corrupted or stuck
    - Windows Update cache contains corrupted files
    - MSI package installation fails during Windows Update process
    - Despite the misleading name mentioning "Visual Studio", this is actually
      a WSL kernel update package that goes through Windows Update infrastructure
    
    SYMPTOMS:
    - WSL update hangs or fails with 0x80070643
    - Docker Desktop can't start because WSL kernel is outdated/broken
    - docker-desktop WSL distro fails with GPU/HCS errors
    
    WORKAROUND:
    Instead of using "wsl --update" which goes through Windows Update,
    we manually download and install the WSL2 kernel MSI package directly.
    This bypasses the corrupted Windows Update infrastructure.
    
    RELEVANT SOURCES:
    - Error 0x80070643 Documentation:
      https://learn.microsoft.com/en-us/answers/questions/4276864/install-error-0x80070643-on-window-11
      
    - WSL GitHub Issues (0x80070643):
      https://github.com/microsoft/WSL/issues/5014
      https://github.com/microsoft/WSL/issues/8749
      
    - WSL Manual Kernel Update Package:
      https://docs.microsoft.com/en-us/windows/wsl/install-manual
      
    - Docker Desktop + WSL Issues:
      https://github.com/docker/for-win/issues/12650
      
    - HCS/GPU Configuration Errors:
      https://github.com/microsoft/WSL/issues/6850
      https://github.com/docker/for-win/issues/12650
      
    - Windows Installer Service Troubleshooting:
      https://support.microsoft.com/en-us/windows/fix-problems-that-block-programs-from-being-installed-or-removed-cca7d1b6-65a9-3d98-426b-e9f927e1eb4d
#>

Write-Host "Trying WSL update alternative method to overcome error 0x80070643 ..." -ForegroundColor Yellow

# Download and install manually to bypass Windows Update
$wslUpdateUrl = "https://wslstorestorage.blob.core.windows.net/wslblob/wsl_update_x64.msi"
$wslMsi = "$env:TEMP\wsl_update_x64.msi"
        
Write-Host "Downloading WSL2 kernel update..." -ForegroundColor Cyan
Invoke-WebRequest -Uri $wslUpdateUrl -OutFile $wslMsi -UseBasicParsing
        
Write-Host "Installing WSL2 kernel..." -ForegroundColor Cyan
Start-Process msiexec.exe -ArgumentList "/i `"$wslMsi`" /quiet /norestart" -Wait
        
Remove-Item $wslMsi -Force -ErrorAction SilentlyContinue

Write-Host "`nWSL2 kernel update completed successfully!" -ForegroundColor Green
Write-Host "`nIMPORTANT: Restart Windows for changes to take effect." -ForegroundColor Yellow
Write-Host "After restart:" -ForegroundColor Cyan
Write-Host "  1. Verify WSL: wsl --version" -ForegroundColor White
Write-Host "  2. Start Docker Desktop" -ForegroundColor White
Write-Host "  3. Docker Desktop will recreate the docker-desktop WSL distro" -ForegroundColor White

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