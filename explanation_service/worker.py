from rq import Worker

from explanation_service.queue import explanation_queue, redis_connection


def main() -> None:
    worker = Worker([explanation_queue], connection=redis_connection)
    worker.work()


if __name__ == "__main__":
    main()
