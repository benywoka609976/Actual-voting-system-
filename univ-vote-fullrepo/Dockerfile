FROM python:3.11-slim
ENV PYTHONUNBUFFERED=1
WORKDIR /app
RUN apt-get update && apt-get install -y build-essential && rm -rf /var/lib/apt/lists/*
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY . .
RUN mkdir -p uploads selfies
EXPOSE 5000
CMD ["gunicorn", "-k", "eventlet", "-w", "1", "app:app", "--bind", "0.0.0.0:5000"]
