<#
.SYNOPSIS
    Disables BitLocker encryption on Windows 11 devices.

.DESCRIPTION
    This script will revert BitLocker encryption on the specified drive(s).
    Requires administrator privileges.
    
.PARAMETER DriveLetter
    The drive letter to disable BitLocker on (e.g., 'C', 'D'). 
    Defaults to 'C' if not specified.

.PARAMETER Force
    If specified, will not prompt for confirmation before disabling BitLocker.

.EXAMPLE
    .\Disable-BitLocker.ps1
    Disables BitLocker on C: drive with confirmation prompt.

.EXAMPLE
    .\Disable-BitLocker.ps1 -DriveLetter D -Force
    Disables BitLocker on D: drive without confirmation.

.NOTES
    Requires administrator privileges.
    Decryption may take considerable time depending on disk size.
#>

param(
    [Parameter(Mandatory = $false)]
    [string]$DriveLetter = 'C',
    
    [Parameter(Mandatory = $false)]
    [switch]$Force
)

# Check if running as administrator
$isAdmin = [Security.Principal.WindowsIdentity]::GetCurrent() | 
    ForEach-Object { [Security.Principal.WindowsPrincipal]::new($_).IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator) }

if (-not $isAdmin) {
    Write-Error "This script must be run as Administrator. Please restart PowerShell as Administrator and try again."
    exit 1
}

# Validate drive letter format
$DriveLetter = $DriveLetter.ToUpper()
if ($DriveLetter -notmatch '^[A-Z]$') {
    Write-Error "Invalid drive letter: $DriveLetter. Please specify a single letter (A-Z)."
    exit 1
}

$drivePath = "$($DriveLetter):"

# Check if BitLocker is enabled on the drive
Write-Host "Checking BitLocker status on $drivePath..." -ForegroundColor Cyan

try {
    $bitlockerStatus = Get-BitLockerVolume -MountPoint $drivePath -ErrorAction Stop
}
catch {
    Write-Error "Failed to get BitLocker status for $drivePath. The drive may not exist or BitLocker module is not available."
    exit 1
}

Write-Host "Current BitLocker Status on $drivePath : $($bitlockerStatus.VolumeStatus)" -ForegroundColor Yellow

if ($bitlockerStatus.VolumeStatus -eq 'FullyDecrypted') {
    Write-Host "$drivePath is already fully decrypted. No action needed." -ForegroundColor Green
    exit 0
}

# Prompt for confirmation if -Force is not specified
if (-not $Force) {
    Write-Host ""
    Write-Warning "This will disable BitLocker encryption on $drivePath"
    Write-Host "Decryption may take a significant amount of time depending on disk size and drive speed." -ForegroundColor Yellow
    
    $confirmation = Read-Host "Do you want to continue? (yes/no)"
    if ($confirmation -ne 'yes') {
        Write-Host "Operation cancelled." -ForegroundColor Yellow
        exit 0
    }
}

# Disable BitLocker
Write-Host "Starting BitLocker decryption on $drivePath..." -ForegroundColor Cyan

try {
    Disable-BitLocker -MountPoint $drivePath -ErrorAction Stop
    Write-Host "BitLocker decryption initiated successfully on $drivePath" -ForegroundColor Green
    Write-Host "The decryption process will continue in the background." -ForegroundColor Yellow
    Write-Host "You can check the progress using: Get-BitLockerVolume -MountPoint $drivePath | Select-Object VolumeStatus, EncryptionPercentage" -ForegroundColor Cyan
}
catch {
    Write-Error "Failed to disable BitLocker on $drivePath : $_"
    exit 1
}

# Display final status
Write-Host ""
$finalStatus = Get-BitLockerVolume -MountPoint $drivePath
Write-Host "BitLocker Status:" -ForegroundColor Cyan
Write-Host "  Volume: $($finalStatus.MountPoint)"
Write-Host "  Status: $($finalStatus.VolumeStatus)"
Write-Host "  Encryption Percentage: $($finalStatus.EncryptionPercentage)%"
