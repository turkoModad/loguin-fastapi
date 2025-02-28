# Usar una imagen oficial de Python como base
FROM python:3.10-slim

# Establecer el directorio de trabajo en /app
WORKDIR /app

# Copiar el archivo de requisitos e instalar dependencias
COPY requirements.txt .
# Instalar dependencias necesarias para psycopg2
RUN apt-get update && apt-get install -y \
    libpq-dev \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir -r requirements.txt

# Copiar el resto de la aplicación al contenedor
COPY . .

# Exponer el puerto 8000 para que se pueda acceder desde fuera del contenedor
EXPOSE 8000

# Comando para ejecutar la aplicación con Uvicorn
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]
