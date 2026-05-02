FROM python:3.10-slim

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY bot ./bot

ENV PYTHONPATH=/app

CMD ["python", "-m", "bot.main"]
