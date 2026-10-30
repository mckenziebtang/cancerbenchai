FROM python:3.12-slim
WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt
COPY app ./app
COPY explanation_service ./explanation_service
COPY retrieval_service ./retrieval_service
COPY agent_service ./agent_service
COPY observability ./observability
COPY frontend ./frontend
COPY literature_data ./literature_data
COPY model_artifacts ./model_artifacts

EXPOSE 8000

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT:-8000} --no-access-log"]
