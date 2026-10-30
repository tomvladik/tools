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
    [string]$NvidiaSmiPath = 'C:\Program Files\NVIDIA Corporation\NVSMI\nvidia-smi.exe',
    [string]$BackupDirectory = "$env:USERPROFILE\Documents\p4-registry-backup"
)

$ErrorActionPreference = 'Stop'
$RegistryClassPath = 'HKLM:\SYSTEM\CurrentControlSet\Control\Class\{4d36e968-e325-11ce-bfc1-08002be10318}'

function Get-GlobFiles {
    param (
        [string]$Pattern,
        [string]$SearchPath = (Get-Location).Path
    )

    $pattern = $Pattern -replace '\*', '.*'
    $pattern = $pattern -replace '\?', '.'

    return (Get-ChildItem -Recurse -File -Filter $Pattern -Path $SearchPath | Select-Object -ExpandProperty FullName)
}

$NvidiaSmiPath = ''
$PossibleNvidiaSmiLocations = 'C:\Program Files\NVIDIA Corporation', 'C:\Program Files (x86)\NVIDIA Corporation' | ForEach-Object -Process {
    Get-GlobFiles -Pattern 'nvidia-smi.exe' -SearchPath $_
}
if ($PossibleNvidiaSmiLocations.Length -eq 0) {
    $NvidiaSmiPath = 'C:\WINDOWS\system32\nvidia-smi.exe'
}
else {
    Write-Host "Found nvidia-smi.exe at: $($PossibleNvidiaSmiLocations[0])"   
    $NvidiaSmiPath = $PossibleNvidiaSmiLocations[0]
}



function Get-GPURegistryKey {
    # Find subkey (0000, 0001, ...), whose DriverDesc contains card name.
    $FoundKeys = Get-ChildItem -Path $RegistryClassPath -ErrorAction SilentlyContinue |
    Where-Object { $_.PSChildName -match '^\d{4}$' } |
    Where-Object {
        $desc = (Get-ItemProperty -Path $_.PSPath -Name DriverDesc -ErrorAction SilentlyContinue).DriverDesc
        $desc -and $desc -like "*$CardName*"
    }
    
    # Validate findings and throw descriptive errors
    if (-not $FoundKeys) { 
        throw "Card '$CardName' not found in registry. Please ensure NVIDIA drivers are installed." 
    }
    
    if (@($FoundKeys).Count -gt 1) { 
        throw "Multiple matches found for '$CardName'. Please specify the exact card model." 
    }
    
    return $FoundKeys[0]
}

function Get-DriverModel {
    if (Test-Path $NvidiaSmiPath) {
        $out = & $NvidiaSmiPath --query-gpu=name,driver_model.current --format=csv,noheader 2>&1
        return ($out | Out-String).Trim()
    }
    return 'nvidia-smi not found'
}

function Show-GPUStatus($RegistryKey) {
    $Props = Get-ItemProperty -Path $RegistryKey.PSPath
    Write-Host ''
    Write-Host "Registry key   : $($RegistryKey.Name)"
    Write-Host "DriverDesc     : $($Props.DriverDesc)"
    Write-Host "AdapterType    : $(if ($null -ne $Props.AdapterType) { $Props.AdapterType } else { '(not set)' })"
    Write-Host "EnableMsHybrid : $(if ($null -ne $Props.EnableMsHybrid) { $Props.EnableMsHybrid } else { '(not set)' })"
    Write-Host "Driver mode:   $(Get-DriverModel)"
    Write-Host ''
}

function Backup-RegistryKey($RegistryKey, $Suffix) {
    New-Item -ItemType Directory -Path $BackupDirectory -Force | Out-Null
    $Stamp = Get-Date -Format 'yyyyMMdd-HHmmss'
    $FilePath = Join-Path $BackupDirectory "p4-$($RegistryKey.PSChildName)-$Suffix-$Stamp.reg"
    $RegPath = $RegistryKey.Name  # HKEY_LOCAL_MACHINE\...
    & reg.exe export $RegPath $FilePath /y | Out-Null
    if ($LASTEXITCODE -ne 0) { throw 'Backup failed, change not applied.' }
    Write-Host "Backup saved: $FilePath"
}

function Request-Restart {
    $Answer = Read-Host 'Change will take effect after restart. Restart now? (y/N)'
    if ($Answer -match '^[yY]') { Restart-Computer -Force }
}

$GPURegistryKey = Get-GPURegistryKey
function Set-Mode {
    param (
        [string]$Mode,
        [int]$WDDMMode = 0,
        [int]$TCCMode = 1
    )

    Backup-RegistryKey $GPURegistryKey 'ORIG'

    if ($Mode -eq 'Gaming') {
        Set-ItemProperty -Path $GPURegistryKey.PSPath -Name 'AdapterType' -Value 1 -Type DWord
        Set-ItemProperty -Path $GPURegistryKey.PSPath -Name 'FeatureScore' -Value 0xd1 -Type DWord
        Set-ItemProperty -Path $GPURegistryKey.PSPath -Name 'EnableMsHybrid' -Value 1 -Type DWord
        Set-ItemProperty -Path $GPURegistryKey.PSPath -Name 'GridLicensedFeatures' -Value 7 -Type DWord
        Write-Host "Set $Mode mode (hybrid graphics + WDDM)."
    }
    else {
        foreach ($PropertyToUnset in 'AdapterType', 'EnableMsHybrid') {
            if ($null -ne (Get-ItemProperty -Path $GPURegistryKey.PSPath -Name $PropertyToUnset -ErrorAction SilentlyContinue).$PropertyToUnset) {
                Remove-ItemProperty -Path $GPURegistryKey.PSPath -Name $PropertyToUnset
            }
        }
        Write-Host "Set $Mode mode (TCC). Games will not work in this mode."
    }

    if (Test-Path $NvidiaSmiPath) {
        $DriverModelValue = if ($Mode -eq 'Gaming') { $WDDMMode } else { $TCCMode }
        & $NvidiaSmiPath -g 0 -dm $DriverModelValue
    }

    Show-GPUStatus $GPURegistryKey
    Backup-RegistryKey $GPURegistryKey 'NEW'
    Request-Restart
}

switch ($Mode) {
    'Status' {
        Show-GPUStatus $GPURegistryKey
    }

    'Gaming' {
        Set-Mode -Mode 'Gaming'
    }

    'Compute' {
        Set-Mode -Mode 'Compute'
    }
}