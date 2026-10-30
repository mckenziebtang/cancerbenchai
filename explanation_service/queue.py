import os

from redis import Redis
from rq import Queue

# Use hosted Redis when REDIS_URL is set, otherwise use local Redis.
REDIS_URL = os.getenv("REDIS_URL", "redis://localhost:6379/0")

redis_connection = Redis.from_url(REDIS_URL, socket_connect_timeout=2, socket_timeout=2)

explanation_queue = Queue(
    "explanations",
    connection=redis_connection,
    default_timeout=300,
)


