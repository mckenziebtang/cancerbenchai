import hashlib

from app.model import MODEL_VERSION
from explanation_service.tasks import EXPLAINER_VERSION


def explanation_cache_key(cell_line_id: str, drug_name: str) -> str:
    return f"explanation:{MODEL_VERSION}:{EXPLAINER_VERSION}:{cell_line_id}:{drug_name}"


def explanation_job_id(cache_key: str) -> str:
    digest = hashlib.sha256(cache_key.encode()).hexdigest()[:24]
    return f"exp_{digest}"
