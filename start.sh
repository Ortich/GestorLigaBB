#!/usr/bin/env bash
set -e

echo "=== Arrancando Gestor de Liga Blood Bowl BB2020 ==="

# 1. Instalar dependencias Python si faltan
if ! python3 -c "import fastapi, sqlmodel, uvicorn" 2>/dev/null; then
  echo "Instalando dependencias de Python..."
  python3 -m pip install -r requirements.txt
fi

# 2. Construir frontend si no existe dist/
if [ ! -d "frontend/dist" ]; then
  echo "Construyendo Frontend React..."
  cd frontend
  npm install
  npm run build
  cd ..
fi

# 3. Inicializar base de datos si no existe
if [ ! -f "bloodbowl.db" ]; then
  echo "Sembrando base de datos inicial con 8 equipos y calendario..."
  python3 seed.py
fi

# 4. Iniciar servidor FastAPI
echo "Iniciando servidor en http://0.0.0.0:8000"
exec python3 -m uvicorn main:app --host 0.0.0.0 --port 8000
