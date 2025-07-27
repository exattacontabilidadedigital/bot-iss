FROM python:3.10

RUN apt-get update && apt-get install -y \
  wget gnupg libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libxss1 libasound2 \
  libxshmfence-dev libgbm-dev libgtk-3-0

RUN pip install playwright && playwright install

WORKDIR /app
COPY . /app

CMD ["python", "server.py"]
