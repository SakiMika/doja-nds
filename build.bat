@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "PYEXE="
set "PYARGS="
where py.exe >nul 2>nul && set "PYEXE=py.exe" && set "PYARGS=-3"
if not defined PYEXE where python.exe >nul 2>nul && set "PYEXE=python.exe"
if not defined PYEXE goto no_python

%PYEXE% %PYARGS% tools\verify_prepared.py --project "."
if errorlevel 1 goto invalid

set "OUTPUT_STEM="
for /f "tokens=3" %%A in ('findstr /b /c:"TARGET := " standalone_game.mk') do set "OUTPUT_STEM=%%A"
if not defined OUTPUT_STEM goto invalid

del /q "%OUTPUT_STEM%.nds" 2>nul

set "DKP_ROOT="
if defined DEVKITPRO if exist "%DEVKITPRO%\msys2\usr\bin\make.exe" set "DKP_ROOT=%DEVKITPRO%"
if not defined DKP_ROOT if exist "D:\devkitPro\msys2\usr\bin\make.exe" set "DKP_ROOT=D:\devkitPro"
if not defined DKP_ROOT if exist "C:\devkitPro\msys2\usr\bin\make.exe" set "DKP_ROOT=C:\devkitPro"
if not defined DKP_ROOT goto no_devkit

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build.ps1" -DkpRoot "%DKP_ROOT%"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" goto failed
if not exist "%OUTPUT_STEM%.nds" (
    echo [ERROR] The toolchain reported success, but %OUTPUT_STEM%.nds was not created.
    pause
    exit /b 1
)

%PYEXE% %PYARGS% tools\verify_nds_runtime.py --nds "%OUTPUT_STEM%.nds"
if errorlevel 1 (
    echo [ERROR] The new ROM is missing required DoJa v59 runtime fixes.
    pause
    exit /b 1
)

echo [OK] ROM created: %OUTPUT_STEM%.nds
pause
exit /b 0

:failed
echo [ERROR] NDS build failed. Error code: %ERR%
pause
exit /b %ERR%

:no_python
echo [ERROR] Python 3 was not found.
pause
exit /b 1

:no_devkit
echo [ERROR] devkitPro MSYS2 make.exe was not found.
echo Set DEVKITPRO or install devkitPro in D:\devkitPro or C:\devkitPro.
pause
exit /b 1

:invalid
echo [ERROR] DoJa v59 Empty has not been prepared with a game,
echo         or the generated data is inconsistent.
echo Run build-doja.bat and select the JAR, JAM, and SP first.
pause
exit /b 1
