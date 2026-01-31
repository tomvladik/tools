<#
    Get Windows Update Log Information
    
    DESCRIPTION:
    Analyzes Windows Update log files to troubleshoot installation errors,
    particularly error 0x80070643 and related MSI installation failures.
    
    LOG FILES ANALYZED:
    1. WindowsUpdate.log - Main Windows Update log (generated from ETL files)
    2. CBS.log - Component-Based Servicing log (installation details)
    3. UpdateSessionOrchestration.etl - Update orchestration events
    4. setupact.log / setuperr.log - Windows setup logs
    
    WHAT IT DOES:
    - Generates readable WindowsUpdate.log from ETL trace files
    - Searches for error codes (0x80070643, etc.)
    - Extracts failed update information
    - Checks CBS.log for MSI installation failures
    - Shows recent update history
    
    ERROR 0x80070643 INDICATORS:
    - MSI installation failures in CBS.log
    - Windows Installer service errors
    - "Visual Studio Client Detector Utility" errors
    - WSL kernel update failures
    
    RELEVANT SOURCES:
    - Windows Update Logs Documentation:
      https://learn.microsoft.com/en-us/windows/deployment/update/windows-update-logs
      
    - Get-WindowsUpdateLog cmdlet:
      https://learn.microsoft.com/en-us/powershell/module/windowsupdate/get-windowsupdatelog
      
    - CBS.log Analysis:
      https://learn.microsoft.com/en-us/troubleshoot/windows-client/deployment/analyze-component-based-servicing-log
#>

#Requires -RunAsAdministrator

Write-Host "`nWindows Update Log Analyzer" -ForegroundColor Cyan
Write-Host "===========================" -ForegroundColor Cyan

# Log file paths
$logsPath = "$env:SystemRoot\Logs\WindowsUpdate"
$cbsLog = "$env:SystemRoot\Logs\CBS\CBS.log"
$usoLogsPath = "$env:ProgramData\USOShared\Logs"
$outputLog = "$env:USERPROFILE\Desktop\WindowsUpdate_Analysis.log"

# Create output file
$timestamp = Get-Date -Format "yyyy-MM-dd HH:mm:ss"
$output = @()
$output += "=" * 80
$output += "Windows Update Log Analysis - $timestamp"
$output += "=" * 80
$output += ""

Write-Host "`n[1/5] Generating WindowsUpdate.log from ETL files..." -ForegroundColor Yellow
Write-Host "This may take 1-2 minutes..." -ForegroundColor Gray

try {
    # Generate WindowsUpdate.log from ETL traces
    $wuLog = "$env:USERPROFILE\Desktop\WindowsUpdate.log"
    Get-WindowsUpdateLog -LogPath $wuLog -ErrorAction Stop | Out-Null
    
    Write-Host "Generated: $wuLog" -ForegroundColor Green
    $output += "WindowsUpdate.log generated at: $wuLog"
    $output += ""
    
    # Search for errors in WindowsUpdate.log
    Write-Host "`n[2/5] Searching for error codes in WindowsUpdate.log..." -ForegroundColor Yellow
    
    $errorPatterns = @(
        '0x80070643',
        '0x8007000d',
        '0x80240034',
        'error',
        'failed',
        'FATAL',
        'WARNING.*failed'
    )
    
    $errors = @()
    foreach ($pattern in $errorPatterns) {
        $matches = Select-String -Path $wuLog -Pattern $pattern -Context 2, 2
        if ($matches) {
            $errors += $matches
        }
    }
    
    if ($errors.Count -gt 0) {
        Write-Host "Found $($errors.Count) error entries" -ForegroundColor Red
        $output += "=" * 80
        $output += "ERRORS FOUND IN WindowsUpdate.log ($($errors.Count) entries)"
        $output += "=" * 80
        
        # Show first 20 errors
        $displayCount = [Math]::Min(20, $errors.Count)
        for ($i = 0; $i -lt $displayCount; $i++) {
            $output += ""
            $output += "Error #$($i + 1):"
            $output += "-" * 40
            $output += $errors[$i].Line
            if ($errors[$i].Context.PreContext) {
                $output += "  Context Before:"
                $errors[$i].Context.PreContext | ForEach-Object { $output += "    $_" }
            }
            if ($errors[$i].Context.PostContext) {
                $output += "  Context After:"
                $errors[$i].Context.PostContext | ForEach-Object { $output += "    $_" }
            }
        }
        
        if ($errors.Count -gt 20) {
            $output += ""
            $output += "... and $($errors.Count - 20) more errors (check full WindowsUpdate.log)"
        }
    }
    else {
        Write-Host "No critical errors found in WindowsUpdate.log" -ForegroundColor Green
        $output += "No critical errors found in WindowsUpdate.log"
    }
    $output += ""
    
}
catch {
    Write-Host "WARNING: Could not generate WindowsUpdate.log" -ForegroundColor Red
    Write-Host "Error: $($_.Exception.Message)" -ForegroundColor Red
    $output += "ERROR: Could not generate WindowsUpdate.log"
    $output += $_.Exception.Message
    $output += ""
}

# Analyze CBS.log for MSI/installation errors
Write-Host "`n[3/5] Analyzing CBS.log for installation errors..." -ForegroundColor Yellow

if (Test-Path $cbsLog) {
    $cbsErrors = Select-String -Path $cbsLog -Pattern '(error|0x80070643|failed.*install|msi.*failed)' -SimpleMatch:$false | Select-Object -Last 50
    
    if ($cbsErrors) {
        Write-Host "Found $($cbsErrors.Count) entries in CBS.log" -ForegroundColor Yellow
        $output += "=" * 80
        $output += "CBS.LOG ERRORS (Component-Based Servicing)"
        $output += "=" * 80
        $output += ""
        
        foreach ($err in $cbsErrors) {
            $output += $err.Line
        }
        $output += ""
    }
    else {
        Write-Host "No errors found in CBS.log" -ForegroundColor Green
        $output += "No recent errors in CBS.log"
        $output += ""
    }
}
else {
    Write-Host "CBS.log not found at $cbsLog" -ForegroundColor Yellow
    $output += "CBS.log not found"
    $output += ""
}

# Check Update Orchestrator logs
Write-Host "`n[4/5] Checking Update Orchestrator logs..." -ForegroundColor Yellow

if (Test-Path $usoLogsPath) {
    $usoLogs = Get-ChildItem -Path $usoLogsPath -Filter "*.etl" -ErrorAction SilentlyContinue
    if ($usoLogs) {
        $output += "=" * 80
        $output += "UPDATE ORCHESTRATOR LOGS"
        $output += "=" * 80
        $output += "Location: $usoLogsPath"
        $output += ""
        foreach ($log in $usoLogs) {
            $output += "  $($log.Name) - $($log.Length) bytes - Modified: $($log.LastWriteTime)"
        }
        $output += ""
        Write-Host "Found $($usoLogs.Count) ETL log files" -ForegroundColor Green
    }
}
else {
    $output += "Update Orchestrator logs not found at $usoLogsPath"
    $output += ""
}

# Get recent Windows Update history
Write-Host "`n[5/5] Retrieving Windows Update history..." -ForegroundColor Yellow

try {
    $updateSession = New-Object -ComObject Microsoft.Update.Session
    $updateSearcher = $updateSession.CreateUpdateSearcher()
    $historyCount = $updateSearcher.GetTotalHistoryCount()
    
    if ($historyCount -gt 0) {
        $history = $updateSearcher.QueryHistory(0, [Math]::Min(20, $historyCount))
        
        $output += "=" * 80
        $output += "RECENT WINDOWS UPDATE HISTORY (Last 20)"
        $output += "=" * 80
        $output += ""
        
        foreach ($entry in $history) {
            $resultCode = switch ($entry.ResultCode) {
                0 { "Not Started" }
                1 { "In Progress" }
                2 { "Succeeded" }
                3 { "Succeeded With Errors" }
                4 { "Failed" }
                5 { "Aborted" }
                default { "Unknown ($($entry.ResultCode))" }
            }
            
            $output += "Date: $($entry.Date)"
            $output += "Title: $($entry.Title)"
            $output += "Result: $resultCode"
            if ($entry.ResultCode -eq 4 -or $entry.ResultCode -eq 3) {
                $output += "HResult: 0x$([Convert]::ToString($entry.HResult, 16).ToUpper())"
            }
            $output += "-" * 80
        }
        $output += ""
        
        # Count failures
        $failures = $history | Where-Object { $_.ResultCode -eq 4 }
        if ($failures) {
            Write-Host "Found $($failures.Count) failed updates" -ForegroundColor Red
        }
        else {
            Write-Host "No failed updates in recent history" -ForegroundColor Green
        }
    }
    else {
        $output += "No update history available"
        $output += ""
    }
    
}
catch {
    Write-Host "Could not retrieve update history: $($_.Exception.Message)" -ForegroundColor Yellow
    $output += "Could not retrieve update history"
    $output += ""
}

# Save output to file
$output | Out-File -FilePath $outputLog -Encoding UTF8

Write-Host "`n" + "=" * 80 -ForegroundColor Cyan
Write-Host "ANALYSIS COMPLETE" -ForegroundColor Green
Write-Host "=" * 80 -ForegroundColor Cyan
Write-Host "`nDetailed report saved to:" -ForegroundColor Yellow
Write-Host "  $outputLog" -ForegroundColor White

if (Test-Path $wuLog) {
    Write-Host "`nFull WindowsUpdate.log saved to:" -ForegroundColor Yellow
    Write-Host "  $wuLog" -ForegroundColor White
}

Write-Host "`nKEY FINDINGS:" -ForegroundColor Cyan
if ($errors.Count -gt 0) {
    Write-Host "  [!] $($errors.Count) errors found in Windows Update logs" -ForegroundColor Red
}
else {
    Write-Host "  [OK] No critical errors in Windows Update logs" -ForegroundColor Green
}

if ($failures) {
    Write-Host "  [!] $($failures.Count) failed update(s) in history" -ForegroundColor Red
    Write-Host "`nMOST RECENT FAILURE:" -ForegroundColor Yellow
    $lastFailure = $failures | Select-Object -First 1
    Write-Host "  Title: $($lastFailure.Title)" -ForegroundColor White
    Write-Host "  Date: $($lastFailure.Date)" -ForegroundColor White
    Write-Host "  Error: 0x$([Convert]::ToString($lastFailure.HResult, 16).ToUpper())" -ForegroundColor Red
}

Write-Host "`nNEXT STEPS:" -ForegroundColor Cyan
Write-Host "  1. Review the detailed report: $outputLog" -ForegroundColor White
Write-Host "  2. Search for specific error codes (0x80070643, etc.)" -ForegroundColor White

Write-Host ""
