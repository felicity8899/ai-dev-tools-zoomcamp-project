FROM python:3.12-slim

WORKDIR /agent
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY responder.py .

EXPOSE 8090
CMD ["uvicorn", "responder:app", "--host", "0.0.0.0", "--port", "8090"]
