.PHONY: up demo down test lint check smoke evaluate
up:
	docker compose up -d --build --wait
demo:
	OTEL_EXPORTER_OTLP_ENDPOINT=http://jaeger:4318 docker compose --profile monitoring up -d --build --wait
down:
	docker compose --profile monitoring down
test:
	python -m pytest -q
lint:
	python -m ruff check .
check:
	python scripts/check_source.py
smoke:
	python scripts/compose_smoke.py
evaluate:
	python -m retrieval_service.evaluate --output literature_data/evaluation_report.json
