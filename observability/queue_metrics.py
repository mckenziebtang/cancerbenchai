"""Read worker aggregates from Redis instead of losing metrics across RQ forks."""

from prometheus_client.core import CounterMetricFamily, GaugeMetricFamily
from redis.exceptions import RedisError


class QueueCollector:
    def __init__(self, connection, queue):
        self.connection = connection
        self.queue = queue

    def collect(self):
        up = GaugeMetricFamily("cancerbench_queue_metrics_available", "Redis metric collection succeeded")
        try:
            keys = ["cache_hits", "cache_misses", "processing_seconds", "processed_jobs", "failed_jobs"]
            values = self.connection.mget([f"explanation:metrics:{name}" for name in keys])
            depth = self.queue.count
            up.add_metric([], 1)
        except (RedisError, ValueError, TypeError):
            up.add_metric([], 0)
            yield up
            return
        yield up
        depth_metric = GaugeMetricFamily("cancerbench_explanation_queue_depth", "Waiting explanation jobs")
        depth_metric.add_metric([], depth)
        yield depth_metric
        for name, value in zip(keys, values):
            metric = CounterMetricFamily(f"cancerbench_explanation_{name}", f"Explanation {name}")
            metric.add_metric([], float(value or 0))
            yield metric
