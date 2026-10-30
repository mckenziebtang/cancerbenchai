from redis import Redis
from rq import Queue, Worker

from explanation_service.queue import REDIS_URL


def main() -> None:
    # Blocking dequeue needs RQ's own read timeout, separate from HTTP Redis calls.
    connection = Redis.from_url(REDIS_URL, socket_connect_timeout=2)
    queue = Queue("explanations", connection=connection)
    worker = Worker([queue], connection=connection)
    worker.work(with_scheduler=True)


if __name__ == "__main__":
    main()
