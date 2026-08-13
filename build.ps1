param(
    [Parameter(Mandatory = $true)]
    [string]$DkpRoot
)

Set-Location -LiteralPath $PSScriptRoot

$make = Join-Path $DkpRoot 'msys2\usr\bin\make.exe'
$cygpath = Join-Path $DkpRoot 'msys2\usr\bin\cygpath.exe'
if (-not (Test-Path -LiteralPath $make)) {
    Write-Host "[ERROR] Missing make.exe: $make"
    exit 1
}

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

$blob = Join-Path $PSScriptRoot 'embedded\doja_scratchpad.lz7b'
if (-not (Test-Path -LiteralPath $blob)) {
    Write-Host '[ERROR] Missing embedded/doja_scratchpad.lz7b. Run build-doja.bat first.'
    exit 2
}

Write-Host ("[CHECK] Embedded ScratchPad wrapper: {0} bytes" -f (Get-Item -LiteralPath $blob).Length)
Write-Host '[CHECK] Runtime expands Nintendo LZ77 before KVM; NitroFS is not used.'
Write-Host '[1/2] Cleaning...'
& $make clean
if ($LASTEXITCODE -ne 0) {
    Write-Host "[ERROR] Clean failed: $LASTEXITCODE"
    exit $LASTEXITCODE
}

Write-Host '[2/2] Building Nintendo DS ROM...'
& $make
$code = [int]$LASTEXITCODE
if ($code -eq 0) {
    Write-Host '[OK] Build completed.'
} else {
    Write-Host "[ERROR] Build failed: $code"
}
exit $code
