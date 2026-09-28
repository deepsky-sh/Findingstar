@echo off
chcp 65001 > nul
cd /d "%~dp0"
set PY=
where python > nul 2>&1 && set PY=python
if not defined PY where py > nul 2>&1 && set PY=py
if not defined PY (
    echo Python이 설치되어 있지 않습니다. https://www.python.org 에서 설치해 주세요.
    echo 설치 화면에서 "Add python.exe to PATH" 를 꼭 체크하세요.
    pause
    exit /b 1
)
%PY% -c "import PySide6, numpy, scipy, PIL, tifffile" > nul 2>&1
if errorlevel 1 (
    echo 처음 실행이라 필요한 패키지를 설치합니다. 잠시만 기다려 주세요...
    %PY% -m pip install -r requirements.txt
    if errorlevel 1 (
        echo 패키지 설치에 실패했습니다. 인터넷 연결을 확인해 주세요.
        pause
        exit /b 1
    )
)
%PY% run.py %*
if errorlevel 1 pause
