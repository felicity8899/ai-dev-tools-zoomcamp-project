# Single-container demo (Hugging Face Spaces / any one-container host).
# The FastAPI backend serves the SPA itself (STATIC_DIR) and runs on SQLite,
# so there is exactly one process and one file of state. See docs/DEPLOYMENT.md.
FROM python:3.12-slim

WORKDIR /app
COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
# SPA files served by the backend's static mount (no nginx in demo mode)
COPY frontend/index.html frontend/app.js frontend/styles.css /app/static/
COPY frontend/lib /app/static/lib

ENV DATABASE_URL=sqlite:////tmp/tablenow.db \
    STATIC_DIR=/app/static

EXPOSE 7860
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
