@echo off
cd /d "%~dp0"
py castel_credcam_qt.py
if errorlevel 1 (
  echo.
  echo La GUI termino con error.
  echo Revisa que Python y los requerimientos esten instalados.
  pause
)
