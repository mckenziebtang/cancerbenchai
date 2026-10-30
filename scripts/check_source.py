"""Dependency-free syntax, formatting, configuration, and asset checks."""

import ast
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DIRECTORIES = ["app", "agent_service", "explanation_service", "retrieval_service", "observability", "deploy", "scripts", "tests"]


def main():
    count = 0
    for directory in DIRECTORIES:
        for path in (ROOT / directory).rglob("*.py"):
            data = path.read_text()
            ast.parse(data, filename=str(path))
            assert not data or data.endswith("\n"), f"Missing final newline: {path}"
            assert not any(line.rstrip() != line for line in data.splitlines()), f"Trailing whitespace: {path}"
            count += 1
    dashboard = json.loads((ROOT / "monitoring/grafana/dashboards/cancerbench.json").read_text())
    assert len(dashboard["panels"]) >= 10
    assert len({p["id"] for p in dashboard["panels"]}) == len(dashboard["panels"])
    subprocess.run(["node", "--check", str(ROOT / "frontend/app.js")], check=True)
    assert "innerHTML" not in (ROOT / "frontend/app.js").read_text()
    print(f"Checked {count} Python files, dashboard JSON, and frontend JavaScript.")


if __name__ == "__main__":
    main()
