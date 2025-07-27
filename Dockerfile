FROM python:3.10

# Instala dependências do sistema necessárias pro Playwright
RUN apt-get update && apt-get install -y \
  wget gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxss1 libasound2 \
  libxshmfence-dev libgbm-dev libgtk-3-0

# Define diretório de trabalho
WORKDIR /app

# Copia os arquivos do projeto
COPY . /app

# Instala dependências Python
RUN pip install --upgrade pip
RUN pip install -r requirements.txt
RUN playwright install

# Define script de entrada
CMD ["python", "server.py"]
