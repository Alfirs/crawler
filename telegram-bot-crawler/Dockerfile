FROM python:3.11-slim

WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

COPY pyproject.toml README.md rates.yaml ./
COPY app ./app
COPY input ./input

RUN pip install --no-cache-dir .

CMD ["python", "-m", "app.main"]
