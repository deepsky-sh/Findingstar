#!/usr/bin/env bash
# StarLab 실행: ./start_mac_linux.sh [사진파일]
cd "$(dirname "$0")"
PY=python3
if ! command -v "$PY" > /dev/null; then
    echo "python3 가 필요합니다. https://www.python.org 에서 설치해 주세요."
    exit 1
fi
if ! "$PY" -c "import PySide6, numpy, scipy, PIL, tifffile" > /dev/null 2>&1; then
    echo "처음 실행이라 필요한 패키지를 설치합니다..."
    "$PY" -m pip install -r requirements.txt || exit 1
fi
exec "$PY" run.py "$@"
