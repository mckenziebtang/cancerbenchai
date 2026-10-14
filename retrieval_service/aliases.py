"""Alias normalization shared by ingestion and retrieval."""

from __future__ import annotations

import re


# Keep this deliberately small and auditable. Add aliases only when the canonical
# name is unambiguous in the CancerBench literature domain.
ALIASES: dict[str, tuple[str, ...]] = {
    "TP53": ("P53", "TRP53", "TUMOR PROTEIN P53"),
    "ERBB2": ("HER2", "NEU"),
    "EGFR": ("ERBB1", "HER1"),
    "BRAF": ("B-RAF",),
    "KRAS": ("K-RAS",),
    "PIK3CA": ("PI3KCA",),
    "CISPLATIN": ("CDDP", "CIS-DIAMMINEDICHLOROPLATINUM"),
    "CARBOPLATIN": ("CBDCA",),
    "PACLITAXEL": ("TAXOL",),
    "DOXORUBICIN": ("ADRIAMYCIN",),
    "FLUOROURACIL": ("5-FU", "5 FLUOROURACIL"),
    "GEFITINIB": ("IRESSA",),
    "ERLOTINIB": ("TARCEVA",),
    "TRASTUZUMAB": ("HERCEPTIN",),
    "OLAPARIB": ("LYNPARZA",),
    "TEMOZOLOMIDE": ("TMZ",),
}

GENES = {"TP53", "ERBB2", "EGFR", "BRAF", "KRAS", "PIK3CA"}
DRUGS = set(ALIASES) - GENES

_CANONICAL_BY_TERM = {
    term.upper(): canonical
    for canonical, aliases in ALIASES.items()
    for term in (canonical, *aliases)
}
_PATTERNS = sorted(_CANONICAL_BY_TERM, key=len, reverse=True)


def normalize_aliases(text: str) -> str:
    """Replace known aliases with canonical symbols/names, case-insensitively."""
    normalized = text
    for term in _PATTERNS:
        normalized = re.sub(
            rf"(?<![A-Za-z0-9]){re.escape(term)}(?![A-Za-z0-9])",
            _CANONICAL_BY_TERM[term],
            normalized,
            flags=re.IGNORECASE,
        )
    return re.sub(r"\s+", " ", normalized).strip()


def extract_normalized_terms(text: str) -> list[str]:
    """Return canonical drug/gene terms found in text in stable order."""
    upper = normalize_aliases(text).upper()
    found = [
        canonical
        for canonical in ALIASES
        if re.search(rf"(?<![A-Z0-9]){re.escape(canonical)}(?![A-Z0-9])", upper)
    ]
    return found


def normalize_filter_term(value: str) -> str:
    """Normalize a filter and reject values outside the curated alias table."""
    canonical = _CANONICAL_BY_TERM.get(value.strip().upper())
    return canonical or value.strip().upper()

