"""Exercise the public compact deployment; never needs an internal token or API key."""

import argparse
import json
import math
import time
import urllib.error
import urllib.request


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--base-url", default="http://127.0.0.1:18004")
    parser.add_argument("--expect-literature", action="store_true")
    args = parser.parse_args()
    base = args.base_url.rstrip("/")

    def request(path, data=None, stream=False):
        body = json.dumps(data).encode() if data is not None else None
        req = urllib.request.Request(base + path, data=body, headers={"Content-Type": "application/json"})
        with urllib.request.urlopen(req, timeout=100) as response:
            raw = response.read().decode()
            return ([json.loads(line) for line in raw.splitlines()] if stream else json.loads(raw)), response.headers

    deadline = time.monotonic() + 180
    while True:
        try:
            assert request("/health")[0]["status"] == "ok"
            break
        except (OSError, ValueError):
            if time.monotonic() >= deadline:
                raise
            time.sleep(1)
    assert "SIDM00001" in request("/catalog")[0]["cell_line_ids"]
    try:
        request("/internal/prediction/health")
    except urllib.error.HTTPError as exc:
        assert exc.code == 404
    else:
        raise AssertionError("Internal routes must not be public")
    payload = {"cell_line_id": "SIDM00001", "drug_name": "Cisplatin", "question": "TP53 cisplatin resistance research"}
    events, headers = request("/research/stream", payload, stream=True)
    result = events[-1]["data"]
    assert any(event["event"] == "progress" for event in events)
    assert math.isfinite(result["prediction"]["prediction"])
    assert result["explanation_status"] == "completed", result
    assert len(result["top_features"]) == 10
    assert result["trace_id"] == headers["x-trace-id"]
    assert request("/research", payload)[0]["explanation_cache_hit"] is True
    if args.expect_literature:
        assert result["citations"], result["limitations"]
    print(json.dumps({"status": "passed", "trace_id": result["trace_id"], "citations": len(result["citations"]), "cache_hit": True}))


if __name__ == "__main__":
    main()
