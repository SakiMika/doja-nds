@echo off
setlocal EnableExtensions DisableDelayedExpansion
cd /d "%~dp0"

set "PYEXE="
set "PYARGS="
where py.exe >nul 2>nul && set "PYEXE=py.exe" && set "PYARGS=-3"
if not defined PYEXE where python.exe >nul 2>nul && set "PYEXE=python.exe"
if not defined PYEXE goto not_prepared

%PYEXE% %PYARGS% tools\verify_prepared.py --project "."
if errorlevel 1 goto not_prepared

set "OUTPUT_STEM="
for /f "tokens=3" %%A in ('findstr /b /c:"TARGET := " standalone_game.mk') do set "OUTPUT_STEM=%%A"
if not defined OUTPUT_STEM goto not_prepared

del /q "*_doja_v*.nds" 2>nul

set "DKP_ROOT="
if defined DEVKITPRO if exist "%DEVKITPRO%\msys2\usr\bin\make.exe" set "DKP_ROOT=%DEVKITPRO%"
if not defined DKP_ROOT if exist "D:\devkitPro\msys2\usr\bin\make.exe" set "DKP_ROOT=D:\devkitPro"
if not defined DKP_ROOT if exist "C:\devkitPro\msys2\usr\bin\make.exe" set "DKP_ROOT=C:\devkitPro"

if not defined DKP_ROOT (
    echo [ERROR] Khong tim thay devkitPro MSYS2 make.exe.
    >"last_build.log" echo [ERROR] Khong tim thay devkitPro MSYS2 make.exe.
    pause
    exit /b 1
)

powershell.exe -NoProfile -ExecutionPolicy Bypass -File "%~dp0build_with_log.ps1" -DkpRoot "%DKP_ROOT%"
set "ERR=%ERRORLEVEL%"

echo.
if not "%ERR%"=="0" goto failed
if not exist "%OUTPUT_STEM%.nds" (
    echo [ERROR] Build bao thanh cong nhung thieu %OUTPUT_STEM%.nds
    pause
    exit /b 1
)
echo [OK] ROM v25: %OUTPUT_STEM%.nds
echo [LOG] last_prepare.log va last_build.log
pause
exit /b 0

:failed
echo [ERROR] Build that bai. Ma loi: %ERR%
echo [LOG] Gui last_prepare.log va last_build.log.
pause
exit /b %ERR%

:not_prepared
echo [ERROR] Chua co bo du lieu v25 hop le.
echo [ERROR] Chi chay build_doja.bat de tao lai game, ScratchPad va metadata.
pause
exit /b 1
