import logging
import sys

import pytest

from retrieval_service.ingest import main


@pytest.mark.parametrize("exported", [False, True])
def test_download_reads_local_env_without_exposing_keys(tmp_path, monkeypatch, caplog, exported):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".env").write_text("NCBI_API_KEY=synthetic-file-key\n")
    monkeypatch.delenv("NCBI_API_KEY", raising=False)
    if exported:
        monkeypatch.setenv("NCBI_API_KEY", "synthetic-exported-key")
    monkeypatch.setattr(sys, "argv", ["ingest", "download"])
    received = []

    def download(manifest, output, api_key):
        received.append(api_key)
        return {"selected_pmids": 0, "abstracts_written": 0}

    monkeypatch.setattr("retrieval_service.ingest.download_manifest", download)
    with caplog.at_level(logging.INFO, logger="cancerbench.ingestion"):
        assert main() == 0
    assert received == ["synthetic-exported-key" if exported else "synthetic-file-key"]
    assert "synthetic-file-key" not in caplog.text
    assert "synthetic-exported-key" not in caplog.text
