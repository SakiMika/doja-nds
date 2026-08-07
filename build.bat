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

del /q "*_doja_v*.nds" 2>nul

set "DKP_ROOT="
if defined DEVKITPRO if exist "%DEVKITPRO%\msys2\usr\bin\make.exe" set "DKP_ROOT=%DEVKITPRO%"
if not defined DKP_ROOT if exist "D:\devkitPro\msys2\usr\bin\make.exe" set "DKP_ROOT=D:\devkitPro"
if not defined DKP_ROOT if exist "C:\devkitPro\msys2\usr\bin\make.exe" set "DKP_ROOT=C:\devkitPro"
if not defined DKP_ROOT goto no_devkit

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_with_log.ps1" -DkpRoot "%DKP_ROOT%"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" goto failed
if not exist "%OUTPUT_STEM%.nds" (
    echo [ERROR] Build bao thanh cong nhung thieu %OUTPUT_STEM%.nds
    pause
    exit /b 1
)
%PYEXE% %PYARGS% tools\verify_nds_runtime.py --nds "%OUTPUT_STEM%.nds"
if errorlevel 1 (
    echo [ERROR] ROM vua build van con runtime cu hoac thieu fix v48.
    pause
    exit /b 1
)
echo [OK] ROM DoJa v48 Empty: %OUTPUT_STEM%.nds
echo [LOG] last_build.log
pause
exit /b 0

:failed
echo [ERROR] Build that bai. Ma loi: %ERR%
echo [LOG] Gui last_build.log.
pause
exit /b %ERR%

:no_python
echo [ERROR] Khong tim thay Python 3.
pause
exit /b 1

:no_devkit
echo [ERROR] Khong tim thay devkitPro MSYS2 make.exe.
pause
exit /b 1

:invalid
echo [ERROR] DoJa v48 Empty chua co game hoac du lieu khong dong bo.
echo [ERROR] Hay chay build-doja.bat de chon JAR, JAM va SP.
pause
exit /b 1
