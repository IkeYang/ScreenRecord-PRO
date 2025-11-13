@echo off
setlocal ENABLEDELAYEDEXPANSION
pushd %~dp0\..

if not exist venv (
  py -3 -m venv venv
)
call venv\Scripts\activate
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install pyinstaller

pyinstaller --noconfirm --clean ^
  --onefile ^
  --name screenrec-cli ^
  --version-file assets\version_file.txt ^
  --manifest assets\app.manifest ^
  main.py

echo Build finished. Output: dist\screenrec-cli.exe
popd
endlocal

