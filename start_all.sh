#!/bin/bash

# Inicia o FastAPI em background
API_KEY=oficinapro2024 FASTAPI_URL=http://localhost:8000 uvicorn app_oficina:app --host 0.0.0.0 --port 8000 &
FASTAPI_PID=$!

# Aguarda o FastAPI iniciar
sleep 3

# Inicia o Express (npm run dev)
API_KEY=oficinapro2024 FASTAPI_URL=http://localhost:8000 npm run dev &
EXPRESS_PID=$!

# Aguarda qualquer um dos processos terminar
wait -n

# Mata ambos os processos ao sair
kill $FASTAPI_PID $EXPRESS_PID 2>/dev/null
