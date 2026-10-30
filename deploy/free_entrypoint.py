"""Supervise the real demo services within a single free web-service instance."""

import json
import os
from pathlib import Path
import secrets
import signal
import subprocess
import sys
import time


def main():
    runtime = Path("/tmp/cancerbench-demo")
    runtime.mkdir(mode=0o700, exist_ok=True)
    pgdata = runtime / "postgres"
    port = int(os.getenv("PORT", "10000"))
    os.environ.update({
        "DATABASE_URL": "postgresql://cancerbench@127.0.0.1:5432/cancerbench",
        "REDIS_URL": "redis://127.0.0.1:6379/0",
        "PREDICTION_URL": f"http://127.0.0.1:{port}/internal/prediction",
        "EXPLANATION_URL": f"http://127.0.0.1:{port}/internal/explanation",
        "RETRIEVAL_URL": f"http://127.0.0.1:{port}/internal/literature",
        "INTERNAL_API_TOKEN": os.getenv("INTERNAL_API_TOKEN") or secrets.token_urlsafe(32),
        "HOSTING_NOTICE": "Free demo: questions run one at a time, and literature reloads after restarts.",
    })
    stopping = False
    children = []

    def stop(signum, frame):
        nonlocal stopping
        stopping = True

    for signum in (signal.SIGTERM, signal.SIGINT):
        signal.signal(signum, stop)

    def launch(name, command):
        process = subprocess.Popen(command, start_new_session=True)
        children.append((name, process))
        return process

    try:
        if not (pgdata / "PG_VERSION").exists():
            subprocess.run([
                "initdb", "-D", str(pgdata), "-U", "cancerbench",
                "--auth-local=trust", "--auth-host=trust", "--encoding=UTF8", "--no-locale",
            ], check=True, stdout=subprocess.DEVNULL)
        launch("postgres", [
            "postgres", "-D", str(pgdata), "-h", "127.0.0.1", "-k", str(runtime),
            "-c", "shared_buffers=16MB", "-c", "max_connections=12",
            "-c", "work_mem=1MB", "-c", "maintenance_work_mem=16MB",
            "-c", "max_parallel_workers=0", "-c", "jit=off",
        ])
        for _ in range(120):
            ready = subprocess.run([
                "pg_isready", "-h", "127.0.0.1", "-U", "cancerbench", "-q",
            ]).returncode == 0
            if ready or stopping:
                break
            time.sleep(0.25)
        if not ready or stopping:
            return 1
        # The database is disposable; its role and local-only sockets are never public.
        exists = subprocess.check_output([
            "psql", "-h", "127.0.0.1", "-U", "cancerbench", "-d", "postgres", "-tAc",
            "SELECT 1 FROM pg_database WHERE datname = 'cancerbench'",
        ]).strip()
        if not exists:
            subprocess.run([
                "createdb", "-h", "127.0.0.1", "-U", "cancerbench", "cancerbench",
            ], check=True)
        launch("redis", [
            "redis-server", "--bind", "127.0.0.1", "--save", "", "--appendonly", "no",
            "--maxmemory", "24mb", "--maxmemory-policy", "noeviction", "--maxclients", "32",
        ])
        for _ in range(120):
            result = subprocess.run(["redis-cli", "ping"], capture_output=True)
            if result.returncode == 0 and b"PONG" in result.stdout:
                break
            if stopping:
                return 1
            time.sleep(0.25)
        else:
            return 1
        launch("worker", [sys.executable, "-m", "explanation_service.worker"])
        launch("web", [
            sys.executable, "-m", "uvicorn", "deploy.combined:create_app", "--factory",
            "--host", "0.0.0.0", "--port", str(port), "--no-access-log", "--limit-concurrency", "24",
        ])
        bootstrap = None
        if os.getenv("DEMO_SKIP_DOWNLOAD") != "1":
            bootstrap = launch("literature-bootstrap", [sys.executable, "-m", "deploy.seed_literature"])
        while not stopping:
            for name, process in children:
                if process is bootstrap:
                    continue
                if process.poll() is not None:
                    print(json.dumps({"event": "demo_service_stopped", "service": name}), flush=True)
                    return 1
            time.sleep(0.5)
        return 0
    finally:
        for _, process in reversed(children):
            if process.poll() is None:
                try:
                    os.killpg(process.pid, signal.SIGTERM)
                except ProcessLookupError:
                    pass
        deadline = time.monotonic() + 10
        for _, process in reversed(children):
            try:
                process.wait(timeout=max(0.1, deadline - time.monotonic()))
            except subprocess.TimeoutExpired:
                try:
                    os.killpg(process.pid, signal.SIGKILL)
                except ProcessLookupError:
                    pass


if __name__ == "__main__":
    raise SystemExit(main())
