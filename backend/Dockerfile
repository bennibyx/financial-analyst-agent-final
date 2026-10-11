FROM python:3.12-slim

# Mirror the repo layout (/app/backend/app and /app/agents) so main.py finds agents/ two folders up.
WORKDIR /app/backend

COPY backend/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY backend/app ./app
COPY agents /app/agents

EXPOSE 8000
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
