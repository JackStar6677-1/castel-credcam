@echo off
cd /d "%~dp0"
py castel_credcam.py
if errorlevel 1 (
  echo.
  echo La aplicacion termino con error.
  echo Si falta OpenCV, ejecuta: py -m pip install -r requirements.txt
  pause
)
