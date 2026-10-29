#Requires -RunAsAdministrator
<#
.SYNOPSIS
    Enable Tesla P4 between gaming (WDDM + hybrid graphics) and compute (TCC) modes.

.PARAMETER Mode
    Gaming  - set AdapterType=1 and EnableMsHybrid=1 in registry, then WDDM
    Compute - remove these values and switch card to TCC (for Ollama/CUDA)
    Status  - just print current status

.EXAMPLE
    powershell -ExecutionPolicy Bypass -File .\tesla-p4-mode.ps1 -Mode Gaming
    powershell -ExecutionPolicy Bypass -File .\tesla-p4-mode.ps1 -Mode Compute
    powershell -ExecutionPolicy Bypass -File .\tesla-p4-mode.ps1 -Mode Status
#>
param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('Gaming', 'Compute', 'Status')]
    [string]$Mode,

    [string]$CardName = 'Tesla P4',
    [string]$NvidiaSmi = 'C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe',
    [string]$BackupDir = "$env:USERPROFILE\Documents\p4-registry-backup"
)

$ErrorActionPreference = 'Stop'
$ClassPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'

function file_glob_search {
    param (
        [string]$pattern,
        [string]$path = (Get-Location).Path
    )

    $pattern = $pattern -replace '\*', '.*'
    $pattern = $pattern -replace '\?', '.'

    $results = Get-ChildItem -Recurse -File -Filter $pattern -Path $path | Select-Object -ExpandProperty FullName

    return $results
}

$NvidiaSmi = ''
$possibleNvidiaSmiLocations = 'C:\Program Files\NVIDIA Corporation', 'C:\Program Files (x86)\NVIDIA Corporation' | ForEach-Object -Process {
    file_glob_search -pattern 'nvidia-smi.exe' -path $_
}
if ($possibleNvidiaSmiLocations.Length -eq 0) {
    $NvidiaSmi = 'C:\WINDOWS\system32\nvidia-smi.exe'
} else {
    echo "Found nvidia-smi.exe at: $($possibleNvidiaSmiLocations[0])"   
    $NvidiaSmi = $possibleNvidiaSmiLocations[0]
}



function Get-CardKey {
    # Find subkey (0000, 0001, ...), whose DriverDesc contains card name.
    $found = Get-ChildItem -Path $ClassPath -ErrorAction SilentlyContinue |
        Where-Object { $_.PSChildName -match '^\d{4}$' } |
        Where-Object {
            $desc = (Get-ItemProperty -Path $_.PSPath -Name DriverDesc -ErrorAction SilentlyContinue).DriverDesc
            $desc -and $desc -like "*$CardName*"
        }
    if (-not $found) { throw "Card '$CardName' not found in registry." }
    if (@($found).Count -gt 1) { throw "Multiple matches found for '$CardName'. Please adjust parameter -CardName." }
    return $found
}

function Get-DriverModel {
    if (Test-Path $NvidiaSmi) {
        $out = & $NvidiaSmi --query-gpu=name,driver_model.current --format=csv,noheader 2>&1
        return ($out | Out-String).Trim()
    }
    return 'nvidia-smi not found'
}

function Show-Status($key) {
    $props = Get-ItemProperty -Path $key.PSPath
    Write-Host ''
    Write-Host "Registry key : $($key.Name)"
    Write-Host "DriverDesc    : $($props.DriverDesc)"
    Write-Host "AdapterType   : $(if ($null -ne $props.AdapterType) { $props.AdapterType } else { '(not set)' })"
    Write-Host "EnableMsHybrid: $(if ($null -ne $props.EnableMsHybrid) { $props.EnableMsHybrid } else { '(not set)' })"
    Write-Host "Driver mode: $(Get-DriverModel)"
    Write-Host ''
}

function Backup-Key($key, $suffix) {
    New-Item -ItemType Directory -Path $BackupDir -Force | Out-Null
    $stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $file = Join-Path $BackupDir "p4-$($key.PSChildName)-$suffix-$stamp.reg"
    $regPath = $key.Name  # HKEY_LOCAL_MACHINE\...
    & reg.exe export $regPath $file /y | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed, change not applied.' }
    Write-Host "Backup saved: $file"
}

function Request-Restart {
    $answer = Read-Host 'Change will take effect after restart. Restart now? (y/N)'
    if ($answer -match '^[yY]') { Restart-Computer -Force }
}

$key = Get-CardKey
function Set-Mode {
    param (
        [string]$Mode,
        [int]$WDDMMode = 0,
        [int]$TCCMode = 1
    )

    Backup-Key $key 'ORIG'

    if ($Mode -eq 'Gaming') {
        Set-ItemProperty -Path $key.PSPath -Name 'AdapterType' -Value 1 -Type DWord
        Set-ItemProperty -Path $key.PSPath -Name 'FeatureScore' -Value 0xd1 -Type DWord
        Set-ItemProperty -Path $key.PSPath -Name 'EnableMsHybrid' -Value 1 -Type DWord
        Set-ItemProperty -Path $key.PSPath -Name 'GridLicensedFeatures' -Value 7 -Type DWord
        Write-Host "Set $Mode mode (hybrid graphics + WDDM)."
    } else {
        foreach ($name in 'AdapterType', 'EnableMsHybrid') {
            if ($null -ne (Get-ItemProperty -Path $key.PSPath -Name $name -ErrorAction SilentlyContinue).$name) {
                Remove-ItemProperty -Path $key.PSPath -Name $name
            }
        }
        Write-Host "Set $Mode mode (TCC). Games will not work in this mode."
    }

    if (Test-Path $NvidiaSmi) {
        $dmValue = if ($Mode -eq 'Gaming') { $WDDMMode } else { $TCCMode }
        & $NvidiaSmi -g 0 -dm $dmValue
    }

    Show-Status $key
    Backup-Key $key 'NEW'
    Request-Restart
}

switch ($Mode) {
    'Status' {
        Show-Status $key
    }

'Gaming' {
    Set-Mode -Mode 'Gaming'
}

'Compute' {
    Set-Mode -Mode 'Compute'
}}