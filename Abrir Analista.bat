@echo off
setlocal

cd /d "%~dp0"

set "APP_URL=http://localhost:8501"
set "PYTHON_CMD=python"

if exist ".venv\Scripts\python.exe" (
    set "PYTHON_CMD=.venv\Scripts\python.exe"
)

echo ============================================
echo  Analista - Cockpit operativo
echo ============================================
echo.
echo Iniciando Streamlit en %APP_URL%
echo Cierra esta ventana para detener la aplicacion.
echo.

start "" "%APP_URL%"

"%PYTHON_CMD%" -m streamlit run ".\app.py" --server.address localhost --server.port 8501

echo.
echo La aplicacion se detuvo.
pause
