@echo off
echo.
echo ╔═══════════════════════════════════════════════╗
echo ║   JORMUNDGANDRSSON — Iniciando sistema        ║
echo ╚═══════════════════════════════════════════════╝
echo.

cd /d "%~dp0backend"

IF NOT EXIST ".env" (
    echo AVISO: No se encontro .env
    copy .env.example .env
    echo.
    echo IMPORTANTE: Edita backend\.env con tus credenciales de Capital.com
    echo Luego vuelve a ejecutar este script.
    echo.
    pause
)

IF NOT EXIST "venv" (
    echo Creando entorno virtual...
    python -m venv venv
)

echo Activando entorno virtual...
call venv\Scripts\activate.bat

echo Instalando dependencias...
pip install -r requirements.txt -q

echo.
echo Servidor iniciado en http://localhost:5000
echo Abre index.html con Live Server en VS Code
echo Presiona Ctrl+C para detener
echo.

python server.py
pause
