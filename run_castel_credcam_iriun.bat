@echo off
cd /d "%~dp0"
py castel_credcam.py --camera-index 0 --backend dshow
if errorlevel 1 (
  echo.
  echo La aplicacion termino con error.
  echo Verifica que Iriun este abierto y conectado en el telefono y en Windows.
  pause
)
