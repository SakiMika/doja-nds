@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo   DoJa v48 Empty - JAR/JAM/SP to Nintendo DS
echo   ScratchPad: automatic Nintendo LZ77 ^(type 0x10^)
echo   game.jar: automatic STORED entries
echo ============================================================
echo.
echo Drag a file into this window or paste its full path, then press Enter.
echo.

set /p "DOJA_JAR=1. JAR file: "
set /p "DOJA_JAM=2. JAM file: "
set /p "DOJA_SP=3. ScratchPad SP file: "
set /p "DOJA_ROM=4. 4-character ROM/save code [D0JA]: "
set /p "DOJA_NAME=5. Optional ROM name [use JAR name]: "
set /p "DOJA_FONT=6. Optional Japanese TTF/TTC font [auto-detect]: "

set "DOJA_JAR=%DOJA_JAR:"=%"
set "DOJA_JAM=%DOJA_JAM:"=%"
set "DOJA_SP=%DOJA_SP:"=%"
set "DOJA_FONT=%DOJA_FONT:"=%"

if not defined DOJA_ROM set "DOJA_ROM=D0JA"

if not exist "%DOJA_JAR%" goto missing
if not exist "%DOJA_JAM%" goto missing
if not exist "%DOJA_SP%" goto missing
if defined DOJA_FONT if not exist "%DOJA_FONT%" goto missing_font

set "PYEXE="
set "PYARGS="

where py.exe >nul 2>nul && set "PYEXE=py.exe" && set "PYARGS=-3"
if not defined PYEXE where python.exe >nul 2>nul && set "PYEXE=python.exe"
if not defined PYEXE goto no_python

rem Remove all generated game data from a previous run.
rem The generic DoJa runtime source itself is not removed.
del /q "*_doja_v48.nds" 2>nul
del /q "unprepared_doja_v48.nds" 2>nul
del /q "embedded\game.jar" 2>nul
del /q "embedded\doja_scratchpad.lz7b" 2>nul
del /q "embedded\osnd_native.pcm" 2>nul
del /q "assets\standalone_icon.bmp" 2>nul
del /q "standalone_game.mk" 2>nul
del /q "include\standalone_game.h" 2>nul
rmdir /s /q "build_doja" 2>nul
rmdir /s /q "build" 2>nul

echo.
echo [1/3] Reading JAM, applying supported bytecode patches, and rebuilding game.jar as STORED...

if defined DOJA_NAME (
    if defined DOJA_FONT (
        %PYEXE% %PYARGS% tools\prepare_doja.py --jar "%DOJA_JAR%" --jam "%DOJA_JAM%" --sp "%DOJA_SP%" --rom-code "%DOJA_ROM%" --name "%DOJA_NAME%" --font "%DOJA_FONT%" > last_prepare.log 2>&1
    ) else (
        %PYEXE% %PYARGS% tools\prepare_doja.py --jar "%DOJA_JAR%" --jam "%DOJA_JAM%" --sp "%DOJA_SP%" --rom-code "%DOJA_ROM%" --name "%DOJA_NAME%" > last_prepare.log 2>&1
    )
) else (
    if defined DOJA_FONT (
        %PYEXE% %PYARGS% tools\prepare_doja.py --jar "%DOJA_JAR%" --jam "%DOJA_JAM%" --sp "%DOJA_SP%" --rom-code "%DOJA_ROM%" --font "%DOJA_FONT%" > last_prepare.log 2>&1
    ) else (
        %PYEXE% %PYARGS% tools\prepare_doja.py --jar "%DOJA_JAR%" --jam "%DOJA_JAM%" --sp "%DOJA_SP%" --rom-code "%DOJA_ROM%" > last_prepare.log 2>&1
    )
)

set "ERR=%ERRORLEVEL%"
type last_prepare.log
if not "%ERR%"=="0" goto prepare_failed

echo.
echo [2/3] Verifying STORED JAR data and Nintendo LZ77 ScratchPad...
%PYEXE% %PYARGS% tools\verify_prepared.py --project "."
if errorlevel 1 goto verify_failed

echo.
echo [3/3] Building the Nintendo DS ROM...
if exist "build-en.bat" (
    call build-en.bat
) else (
    call build.bat
)
exit /b %ERRORLEVEL%

:missing
echo.
echo [ERROR] The selected JAR, JAM, or SP file could not be found.
pause
exit /b 1

:missing_font
echo.
echo [ERROR] The selected font file could not be found.
pause
exit /b 1

:no_python
echo.
echo [ERROR] Python 3 was not found.
echo Install Python 3 and Pillow:
echo     py -3 -m pip install pillow
pause
exit /b 1

:prepare_failed
echo.
echo [ERROR] Game preparation failed.
echo Please check or send: last_prepare.log
pause
exit /b %ERR%

:verify_failed
echo.
echo [ERROR] Prepared data failed verification.
echo The LZ77 ScratchPad/JAR output is not synchronized, so the ROM will not be built.
pause
exit /b 1
