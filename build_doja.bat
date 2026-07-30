@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

echo ================================================
echo   DoJa i-appli to Nintendo DS - Full-Screen + Latin Font Fix v36
echo ================================================
echo.
set /p "DOJA_JAR=Duong dan file JAR: "
set /p "DOJA_JAM=Duong dan file JAM: "
set /p "DOJA_SP=Duong dan file SP: "
set /p "DOJA_ROM=Ma ROM 4 ky tu ban muon tao: "
set /p "DOJA_FONT=Font Nhat TTF/TTC (Enter de tu tim font Windows): "

if not exist "%DOJA_JAR%" goto missing
if not exist "%DOJA_JAM%" goto missing
if not exist "%DOJA_SP%" goto missing

set "PYEXE="
set "PYARGS="
where py.exe >nul 2>nul && set "PYEXE=py.exe" && set "PYARGS=-3"
if not defined PYEXE where python.exe >nul 2>nul && set "PYEXE=python.exe"
if not defined PYEXE (
    echo [ERROR] Khong tim thay Python 3.
    echo Cai Python va Pillow: py -3 -m pip install pillow
    pause
    exit /b 1
)

rem Never build generated files or ROMs left by any older DoJa revision.
del /q "*_doja_v*.nds" 2>nul
del /q "unprepared_doja_v36.nds" 2>nul
del /q "embedded\game.jar" 2>nul
del /q "embedded\doja_scratchpad.bin" 2>nul
del /q "assets\standalone_icon.bmp" 2>nul
del /q "standalone_game.mk" 2>nul
del /q "include\standalone_game.h" 2>nul
del /q "build_doja\prepared_v36.ok" 2>nul
del /q "build_doja\doja_scratchpad.bin" 2>nul

if defined DOJA_FONT (
    %PYEXE% %PYARGS% tools\prepare_doja.py --jar "%DOJA_JAR%" --jam "%DOJA_JAM%" --sp "%DOJA_SP%" --rom-code "%DOJA_ROM%" --font "%DOJA_FONT%" > last_prepare.log 2>&1
) else (
    %PYEXE% %PYARGS% tools\prepare_doja.py --jar "%DOJA_JAR%" --jam "%DOJA_JAM%" --sp "%DOJA_SP%" --rom-code "%DOJA_ROM%" > last_prepare.log 2>&1
)
set "ERR=%ERRORLEVEL%"
type last_prepare.log
if not "%ERR%"=="0" (
    echo [ERROR] Chuan bi game that bai. Gui last_prepare.log.
    pause
    exit /b %ERR%
)

%PYEXE% %PYARGS% tools\verify_prepared.py --project "."
set "ERR=%ERRORLEVEL%"
if not "%ERR%"=="0" (
    echo [ERROR] Source/JAR/metadata khong dong bo v36. Khong build.
    pause
    exit /b %ERR%
)

call build.bat
exit /b %ERRORLEVEL%

:missing
echo [ERROR] Mot trong cac file JAR/JAM/SP khong ton tai.
pause
exit /b 1
