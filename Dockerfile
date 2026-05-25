FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Install Python deps first (cached layer)
COPY requirements.txt ./
RUN pip install -r requirements.txt

# Copy the rest of the app (data/, src/, ml_models/, templates/, scripts/, tests/)
COPY . .

# Railway provides $PORT — default 8000 locally.
ENV PORT=8000
EXPOSE 8000

CMD ["sh", "-c", "uvicorn src.main:app --host 0.0.0.0 --port ${PORT:-8000}"]
