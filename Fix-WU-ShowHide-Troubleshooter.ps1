<#
    FIX: Windows Update - Show or Hide Updates
    
    ISSUE: Problematic Windows Updates that keep failing or cause issues
    Error 0x80070643 and other installation errors that loop endlessly
    
    TOOL: Microsoft's Official "Show or Hide Updates" Troubleshooter
    This diagnostic tool allows you to:
    - Hide specific Windows Updates that are causing problems
    - Show previously hidden updates
    - Prevent problematic updates from reinstalling automatically
    
    USE CASES:
    - Update fails repeatedly with same error (e.g., 0x80070643)
    - Update is already installed but keeps appearing
    - Update causes system instability or compatibility issues
    - Need to temporarily block an update until a fix is released
    
    HOW IT WORKS:
    1. Download the official Microsoft troubleshooter (.diagcab file)
    2. Run the troubleshooter - it will scan for available/failed updates
    3. Choose "Hide updates" option
    4. Select which updates to hide from the list
    5. Hidden updates won't be installed automatically anymore
    
    RELEVANT SOURCES:
    - Official Download:
      https://download.microsoft.com/download/F/2/2/F22D5FDB-59CD-4275-8C95-1BE17BF70B21/wushowhide.diagcab
      
    - Error 0x80070643 Troubleshooting:
      https://learn.microsoft.com/en-us/answers/questions/4276864/install-error-0x80070643-on-window-11
      
    - Windows Update Troubleshooting:
      https://support.microsoft.com/en-us/windows/fix-problems-that-block-programs-from-being-installed-or-removed-cca7d1b6-65a9-3d98-426b-e9f927e1eb4d
#>

Write-Host "`nWindows Update - Show or Hide Updates Troubleshooter" -ForegroundColor Cyan
Write-Host "=====================================================" -ForegroundColor Cyan

# Official Microsoft troubleshooter URL
$troubleshooterUrl = "https://download.microsoft.com/download/F/2/2/F22D5FDB-59CD-4275-8C95-1BE17BF70B21/wushowhide.diagcab"
$troubleshooterFile = "$env:TEMP\wushowhide.diagcab"

try {
    Write-Host "`nDownloading Windows Update troubleshooter..." -ForegroundColor Yellow
    Invoke-WebRequest -Uri $troubleshooterUrl -OutFile $troubleshooterFile -UseBasicParsing
    
    Write-Host "Download completed successfully!" -ForegroundColor Green
    Write-Host "`nLaunching troubleshooter..." -ForegroundColor Cyan
    Write-Host ""
    Write-Host "INSTRUCTIONS:" -ForegroundColor Yellow
    Write-Host "  1. Click 'Next' in the troubleshooter window" -ForegroundColor White
    Write-Host "  2. Wait for it to detect update issues" -ForegroundColor White
    Write-Host "  3. Choose 'Hide updates' to block problematic updates" -ForegroundColor White
    Write-Host "  4. Select the updates you want to hide from the list" -ForegroundColor White
    Write-Host "  5. Click 'Next' to apply the changes" -ForegroundColor White
    Write-Host ""
    Write-Host "NOTE: Hidden updates won't install automatically anymore." -ForegroundColor Cyan
    Write-Host "      You can run this tool again and choose 'Show hidden updates' to unhide them." -ForegroundColor Cyan
    Write-Host ""
    
    # Launch the troubleshooter
    Start-Process -FilePath $troubleshooterFile -Wait
    
    Write-Host "`nTroubleshooter completed!" -ForegroundColor Green
    
    # Cleanup
    Remove-Item $troubleshooterFile -Force -ErrorAction SilentlyContinue
}
catch {
    Write-Host "`nERROR: Failed to download or run troubleshooter" -ForegroundColor Red
    Write-Host "Error details: $($_.Exception.Message)" -ForegroundColor Red
    Write-Host "`nYou can manually download it from:" -ForegroundColor Yellow
    Write-Host $troubleshooterUrl -ForegroundColor White
}

Write-Host "`nDone!" -ForegroundColor Green
