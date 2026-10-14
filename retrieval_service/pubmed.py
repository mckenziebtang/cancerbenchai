"""Reproducible PubMed download support using the public NCBI E-utilities API."""

from __future__ import annotations

import json
import time
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from datetime import date
from pathlib import Path
from typing import Any


EUTILS = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"


def _request(endpoint: str, params: dict[str, Any], api_key: str | None = None) -> bytes:
    query = {"tool": "cancerbench", "email": "cancerbench@example.invalid", **params}
    if api_key:
        query["api_key"] = api_key
    url = f"{EUTILS}/{endpoint}?{urllib.parse.urlencode(query)}"
    with urllib.request.urlopen(url, timeout=60) as response:
        return response.read()


def search_pmids(query: str, limit: int, api_key: str | None = None) -> list[str]:
    payload = _request(
        "esearch.fcgi",
        {"db": "pubmed", "term": query, "retmode": "json", "retmax": limit, "sort": "relevance"},
        api_key,
    )
    result = json.loads(payload)["esearchresult"]
    return [str(pmid) for pmid in result.get("idlist", [])]


def fetch_articles(
    pmids: list[str], selection_queries: dict[str, str], api_key: str | None = None
) -> list[dict[str, Any]]:
    if not pmids:
        return []
    root = ET.fromstring(
        _request(
            "efetch.fcgi",
            {"db": "pubmed", "id": ",".join(pmids), "retmode": "xml"},
            api_key,
        )
    )
    records: list[dict[str, Any]] = []
    today = date.today().isoformat()
    for item in root.findall(".//PubmedArticle"):
        citation = item.find("MedlineCitation")
        article = citation.find("Article") if citation is not None else None
        if citation is None or article is None:
            continue
        pmid = _text(citation.find("PMID"))
        title = _all_text(article.find("ArticleTitle"))
        abstract_parts = []
        for part in article.findall("Abstract/AbstractText"):
            value = _all_text(part)
            label = part.attrib.get("Label")
            abstract_parts.append(f"{label}: {value}" if label else value)
        abstract = " ".join(part for part in abstract_parts if part)
        if not pmid or not title or not abstract:
            continue
        journal = _all_text(article.find("Journal/Title")) or None
        year_text = (
            _text(article.find("Journal/JournalIssue/PubDate/Year"))
            or _text(article.find("ArticleDate/Year"))
        )
        if not year_text:
            medline_date = _text(article.find("Journal/JournalIssue/PubDate/MedlineDate"))
            year_text = medline_date[:4] if medline_date else None
        authors = []
        for author in article.findall("AuthorList/Author"):
            collective = _text(author.find("CollectiveName"))
            name = " ".join(
                value for value in (_text(author.find("ForeName")), _text(author.find("LastName"))) if value
            )
            if collective or name:
                authors.append(collective or name)
        doi = None
        for identifier in item.findall("PubmedData/ArticleIdList/ArticleId"):
            if identifier.attrib.get("IdType") == "doi":
                doi = _text(identifier)
                break
        records.append(
            {
                "pmid": pmid,
                "doi": doi,
                "title": title,
                "abstract": abstract,
                "authors": authors,
                "year": int(year_text) if year_text and year_text[:4].isdigit() else None,
                "journal": journal,
                "url": f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
                "ingestion_date": today,
                "selection_query": selection_queries[pmid],
            }
        )
    return records


def download_manifest(
    manifest_path: Path,
    output_path: Path,
    api_key: str | None = None,
) -> dict[str, int]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    selected: dict[str, str] = {}
    for spec in manifest["queries"]:
        for pmid in search_pmids(spec["query"], int(spec["limit"]), api_key):
            selected.setdefault(pmid, spec["query"])
        # NCBI permits three requests/second without an API key.
        time.sleep(0.11 if api_key else 0.35)

    articles: list[dict[str, Any]] = []
    pmids = list(selected)
    for start in range(0, len(pmids), 100):
        articles.extend(fetch_articles(pmids[start : start + 100], selected, api_key))
        time.sleep(0.11 if api_key else 0.35)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        "".join(json.dumps(article, ensure_ascii=False) + "\n" for article in articles),
        encoding="utf-8",
    )
    return {"selected_pmids": len(selected), "abstracts_written": len(articles)}


def _text(element: ET.Element | None) -> str:
    return (element.text or "").strip() if element is not None else ""


def _all_text(element: ET.Element | None) -> str:
    return "".join(element.itertext()).strip() if element is not None else ""

