@echo off
cd /d "%~dp0"
set "PYTHON_EXE=%~dp0..\.venv\Scripts\python.exe"
if not exist "%PYTHON_EXE%" (
  echo [ERROR] No existe el entorno local: %PYTHON_EXE%
  echo Ejecuta desde la raiz: py -m venv .venv ^& .venv\Scripts\python.exe -m pip install -r requirements.txt
  pause
  exit /b 1
)
"%PYTHON_EXE%" castel_credcam_qt.py
if errorlevel 1 (
  echo.
  echo La GUI termino con error.
  echo Revisa que el entorno .venv y los requerimientos esten instalados.
  pause
)
