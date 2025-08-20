# Imagen base oficial de Python
FROM mcr.microsoft.com/vscode/devcontainers/python:3.11

# Instalar dependencias del sistema necesarias
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    poppler-utils \
    tesseract-ocr \
    libtesseract-dev \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario vscode (ya viene en la base) y configurar entorno
USER vscode
WORKDIR /workspace
