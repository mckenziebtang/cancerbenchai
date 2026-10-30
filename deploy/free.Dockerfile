FROM python:3.12-slim-bookworm AS python-runtime
FROM pgvector/pgvector:pg17-bookworm

COPY --from=python-runtime /usr/local /usr/local
RUN apt-get update && apt-get install -y --no-install-recommends \
    redis-server libbz2-1.0 libexpat1 libffi8 libgdbm6 liblzma5 libncursesw6 \
    libreadline8 libsqlite3-0 libssl3 libuuid1 zlib1g libgomp1 \
    && rm -rf /var/lib/apt/lists/* && ldconfig && python --version

ENV PYTHONUNBUFFERED=1 PYTHONDONTWRITEBYTECODE=1 \
    OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 MKL_NUM_THREADS=1 NUMEXPR_NUM_THREADS=1
WORKDIR /app
COPY requirements.txt .
# This deployment runs CPU inference only; retain the exact XGBoost version.
RUN sed 's/^xgboost==/xgboost-cpu==/' requirements.txt > /tmp/requirements-free.txt \
    && pip install --no-cache-dir -r /tmp/requirements-free.txt
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates \
    && rm -rf /var/lib/apt/lists/* && update-ca-certificates
COPY app ./app
COPY explanation_service ./explanation_service
COPY retrieval_service ./retrieval_service
COPY agent_service ./agent_service
COPY observability ./observability
COPY frontend ./frontend
COPY literature_data ./literature_data
COPY model_artifacts ./model_artifacts
COPY deploy ./deploy

USER postgres
EXPOSE 10000
ENTRYPOINT ["python", "-m", "deploy.free_entrypoint"]
