param(
    [Parameter(Mandatory = $true)]
    [string]$DkpRoot
)

Set-Location -LiteralPath $PSScriptRoot
$make = Join-Path $DkpRoot 'msys2\usr\bin\make.exe'
$cygpath = Join-Path $DkpRoot 'msys2\usr\bin\cygpath.exe'
if (-not (Test-Path -LiteralPath $make)) { Write-Host "[ERROR] Missing make.exe: $make"; exit 1 }

$dkpPosix = $null
if (Test-Path -LiteralPath $cygpath) {
    $dkpPosix = (& $cygpath -u $DkpRoot 2>$null | Select-Object -First 1)
    if ($null -ne $dkpPosix) { $dkpPosix = $dkpPosix.ToString().Trim() }
}
if ([string]::IsNullOrWhiteSpace($dkpPosix)) {
    $drive = [System.IO.Path]::GetPathRoot($DkpRoot).Substring(0, 1).ToLowerInvariant()
    $tail = $DkpRoot.Substring(3).Replace('\', '/')
    $dkpPosix = "/$drive/$tail"
}

$env:PATH = "$(Join-Path $DkpRoot 'msys2\usr\bin');$(Join-Path $DkpRoot 'devkitARM\bin');$(Join-Path $DkpRoot 'tools\bin');$env:PATH"
$env:DEVKITPRO = $dkpPosix
$env:DEVKITARM = "$dkpPosix/devkitARM"

$logDir = Join-Path $PSScriptRoot 'build_logs'
New-Item -ItemType Directory -Force -Path $logDir | Out-Null
$stamp = Get-Date -Format 'yyyyMMdd_HHmmss'
$lastLog = Join-Path $PSScriptRoot 'last_build.log'
$archiveLog = Join-Path $logDir ("build_{0}.log" -f $stamp)
$utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$newLine = [Environment]::NewLine
$header = @(
    'DoJa v41 native viewport + game-independent preparation + SAV build log'
    "Time: $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')"
    "Project: $PSScriptRoot"
    "DEVKITPRO MSYS2: $dkpPosix"
    '============================================================'
)
[System.IO.File]::WriteAllLines($lastLog, $header, $utf8NoBom)
[System.IO.File]::AppendAllText($lastLog, "Port version: v41$([Environment]::NewLine)", $utf8NoBom)

function Write-LogLine([AllowEmptyString()][string]$Text) {
    Write-Host $Text
    [System.IO.File]::AppendAllText($lastLog, $Text + $newLine, $utf8NoBom)
}
function Invoke-NativeLogged([string]$Executable, [string[]]$Arguments = @()) {
    & $Executable @Arguments 2>&1 | ForEach-Object { Write-LogLine ([string]$_) }
    return [int]$LASTEXITCODE
}

# v41: restore the native ScratchPad before make starts.  This catches source
# overlays and accidental deletion without ever falling back to the old JAR
# resource path that exhausted the KVM heap.
$nativeSp = Join-Path $PSScriptRoot 'embedded\doja_scratchpad.bin'
$nativeSpBackup = Join-Path $PSScriptRoot 'build_doja\doja_scratchpad.bin'
if (-not (Test-Path -LiteralPath $nativeSp) -and (Test-Path -LiteralPath $nativeSpBackup)) {
    New-Item -ItemType Directory -Force -Path (Split-Path -Parent $nativeSp) | Out-Null
    Copy-Item -LiteralPath $nativeSpBackup -Destination $nativeSp -Force
    Write-LogLine '[RESTORE] Native ScratchPad restored from build_doja backup.'
}
if (-not (Test-Path -LiteralPath $nativeSp)) {
    Write-LogLine '[ERROR] Missing embedded/doja_scratchpad.bin and no backup exists.'
    Write-LogLine '[ERROR] Run build_doja.bat again; do not build stale generated files.'
    Copy-Item $lastLog $archiveLog -Force
    exit 2
}
$nativeSpSize = (Get-Item -LiteralPath $nativeSp).Length
Write-LogLine ("[CHECK] Native ScratchPad: {0} bytes" -f $nativeSpSize)
if ($nativeSpSize -le 0) {
    Write-LogLine '[ERROR] Native ScratchPad is empty.'
    Copy-Item $lastLog $archiveLog -Force
    exit 2
}

Write-LogLine '[1/2] Cleaning...'
$cleanCode = Invoke-NativeLogged $make @('clean')
if ($cleanCode -ne 0) {
    Write-LogLine "[ERROR] Clean failed: $cleanCode"
    Copy-Item $lastLog $archiveLog -Force
    exit $cleanCode
}
Write-LogLine '[2/2] Building DoJa standalone ROM...'
$buildCode = Invoke-NativeLogged $make
if ($buildCode -eq 0) { Write-LogLine '[OK] Build completed.' }
else { Write-LogLine "[ERROR] Build failed: $buildCode" }
Copy-Item $lastLog $archiveLog -Force
Write-Host "[LOG] $lastLog"
Write-Host "[ARCHIVE LOG] $archiveLog"
exit $buildCode
