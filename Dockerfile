FROM python:3.11-slim

ARG CACHEBUST=2

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY main.py .

ENV PYTHONUNBUFFERED=1

EXPOSE 7860

CMD ["python", "main.py"]
