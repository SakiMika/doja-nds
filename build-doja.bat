@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

echo ============================================================
echo   DoJa v48 Empty - JAR/JAM/SP to Nintendo DS
echo   ScratchPad: automatic Nintendo LZ77 ^(0x10^)
echo   game.jar: automatic STORED entries
echo ============================================================
echo.
echo Keo file vao cua so nay hoac dan duong dan, sau do nhan Enter.
set /p "DOJA_JAR=1. File JAR: "
set /p "DOJA_JAM=2. File JAM: "
set /p "DOJA_SP=3. File SP: "
set /p "DOJA_ROM=4. Ma save 4 ky tu [D0JA]: "
set /p "DOJA_NAME=5. Ten ROM tuy chon [lay ten JAR]: "
set /p "DOJA_FONT=6. Font Nhat TTF/TTC tuy chon [tu tim]: "

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

rem Remove every generated game from an earlier run. The runtime source stays.
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
echo [1/3] Dang doc JAM, va bytecode neu dung chu ky, va tao game.jar STORED...
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
echo [2/3] Dang kiem tra JAR STORED va ScratchPad LZ77...
%PYEXE% %PYARGS% tools\verify_prepared.py --project "."
if errorlevel 1 goto verify_failed

echo.
echo [3/3] Dang build ROM NDS...
call build.bat
exit /b %ERRORLEVEL%

:missing
echo [ERROR] Khong tim thay JAR, JAM hoac SP.
pause
exit /b 1

:missing_font
echo [ERROR] Khong tim thay file font da chon.
pause
exit /b 1

:no_python
echo [ERROR] Khong tim thay Python 3.
echo Cai Python va Pillow: py -3 -m pip install pillow
pause
exit /b 1

:prepare_failed
echo [ERROR] Chuan bi game that bai. Gui last_prepare.log.
pause
exit /b %ERR%

:verify_failed
echo [ERROR] Du lieu sau khi nen LZ77 khong dong bo. Khong build.
pause
exit /b 1
