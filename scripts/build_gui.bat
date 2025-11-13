@echo off
setlocal ENABLEDELAYEDEXPANSION
pushd %~dp0\..

REM Create venv if missing (optional)
if not exist venv (
  py -3 -m venv venv
)
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

set ICON_ARG=
if exist assets\app.ico (
  set ICON_ARG=--icon assets\app.ico
  echo Using icon: assets\app.ico
) else (
  echo [WARN] assets\app.ico not found. Building without custom icon.
)

pyinstaller --noconfirm --clean ^
  --onefile --windowed ^
  --name ScreenRecorder ^
  !ICON_ARG! ^
  --version-file assets\version_file.txt ^
  --manifest assets\app.manifest ^
  --hidden-import pynput.keyboard._win32 ^
  --hidden-import pynput.mouse._win32 ^
  run_gui.py

echo Build finished. Output: dist\ScreenRecorder.exe
popd
endlocal

