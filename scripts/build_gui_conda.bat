@echo off
REM Build using the currently active conda environment (no extra venv).
setlocal
pushd %~dp0\..

where pyinstaller >nul 2>nul
if %errorlevel% neq 0 (
  echo Installing pyinstaller into current environment...
  python -m pip install --upgrade pip
  pip install pyinstaller
)

if exist assets\app.ico (
  echo Using icon: assets\app.ico
  set ICON_ARG=--icon assets\app.ico
) else (
  set ICON_ARG=
)

pyinstaller --noconfirm --clean ^
  --onefile --windowed ^
  --name ScreenRecorder ^
  %ICON_ARG% ^
  --version-file assets\version_file.txt ^
  --manifest assets\app.manifest ^
  --hidden-import pynput.keyboard._win32 ^
  --hidden-import pynput.mouse._win32 ^
  run_gui.py

echo Build finished. Output: dist\ScreenRecorder.exe
popd
endlocal

