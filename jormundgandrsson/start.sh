#!/bin/bash
# ═══════════════════════════════════════════════════════
# JORMUNDGANDRSSON — Script de inicio (Mac/Linux)
# ═══════════════════════════════════════════════════════

echo ""
echo "╔═══════════════════════════════════════════════╗"
echo "║   JORMUNDGANDRSSON — Iniciando sistema        ║"
echo "╚═══════════════════════════════════════════════╝"
echo ""

# Verificar Python
if ! command -v python3 &> /dev/null; then
    echo "ERROR: Python3 no encontrado. Instala Python 3.8+"
    exit 1
fi

# Ir a la carpeta backend
cd "$(dirname "$0")/backend"

# Verificar .env
if [ ! -f ".env" ]; then
    echo "AVISO: No se encontró .env"
    echo "Copiando .env.example → .env"
    cp .env.example .env
    echo ""
    echo "IMPORTANTE: Edita backend/.env con tus credenciales de Capital.com"
    echo "Luego vuelve a ejecutar este script."
    echo ""
    read -p "Presiona Enter para continuar de todas formas..."
fi

# Instalar dependencias si no existen
if [ ! -d "venv" ]; then
    echo "Creando entorno virtual..."
    python3 -m venv venv
fi

echo "Activando entorno virtual..."
source venv/bin/activate

echo "Instalando dependencias..."
pip install -r requirements.txt -q

echo ""
echo "Iniciando servidor en http://localhost:5000"
echo "Abre index.html con Live Server en VS Code"
echo "Presiona Ctrl+C para detener"
echo ""

python3 server.py
