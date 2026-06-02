@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] No existe el entorno local: %PYTHON_EXE%
  echo Ejecuta: py -m venv .venv ^& .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
"%PYTHON_EXE%" castel_credcam.py --backend dshow
if errorlevel 1 (
  echo.
  echo La aplicacion termino con error.
  echo Verifica que Iriun este abierto y conectado en el telefono y en Windows.
  pause
)
