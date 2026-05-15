# coding: utf8
import logging
from itertools import chain

import six
from flask import Response, request
from locust import events
from locust import runners as locust_runners
from locust import stats as locust_stats
from prometheus_client import Metric, REGISTRY, exposition

from config.config_settings import LoadTestConfig


LOGGER = logging.getLogger(__name__)
_COLLECTOR_REGISTERED = False


class LocustCollector:
    registry = REGISTRY

    def __init__(self, environment, runner):
        self.environment = environment
        self.runner = runner

    def collect(self):
        runner = self.runner
        if runner and runner.state in (locust_runners.STATE_SPAWNING, locust_runners.STATE_RUNNING):
            stats = []
            for stat in chain(locust_stats.sort_stats(runner.stats.entries), [runner.stats.total]):
                stats.append(
                    {
                        "method": stat.method,
                        "name": stat.name,
                        "num_requests": stat.num_requests,
                        "num_failures": stat.num_failures,
                        "avg_response_time": stat.avg_response_time,
                        "min_response_time": stat.min_response_time or 0,
                        "max_response_time": stat.max_response_time,
                        "current_rps": stat.current_rps,
                        "median_response_time": stat.median_response_time,
                        "ninetieth_response_time": stat.get_response_time_percentile(0.9),
                        "avg_content_length": stat.avg_content_length,
                        "current_fail_per_sec": stat.current_fail_per_sec,
                    }
                )

            metric = Metric("locust_user_count", "Swarmed users", "gauge")
            metric.add_sample("locust_user_count", value=runner.user_count, labels={})
            yield metric

            stats_metrics = [
                "num_requests",
                "num_failures",
                "avg_response_time",
                "ninetieth_response_time",
                "current_rps",
            ]
            for metric_name in stats_metrics:
                metric_type = "gauge"
                if metric_name in ["num_requests", "num_failures"]:
                    metric_type = "counter"

                metric = Metric(f"locust_stats_{metric_name}", f"Locust stats {metric_name}", metric_type)
                for stat in stats:
                    method = stat["method"] if stat["name"] != "Aggregated" else "Aggregated"
                    metric.add_sample(
                        f"locust_stats_{metric_name}",
                        value=stat[metric_name],
                        labels={"path": stat["name"], "method": method},
                    )
                yield metric

            for _error in six.itervalues(runner.stats.errors):
                # Keep compatibility with old exporter shape without exposing unused variables.
                pass


@events.init.add_listener
def locust_init(environment, runner, **kwargs):
    global _COLLECTOR_REGISTERED

    if not LoadTestConfig.ENABLE_PROMETHEUS:
        return

    if not (environment.web_ui and runner):
        return

    @environment.web_ui.app.route("/metrics")
    def prometheus_exporter():
        encoder, content_type = exposition.choose_encoder(request.headers.get("Accept"))
        body = encoder(REGISTRY)
        return Response(body, content_type=content_type)

    if _COLLECTOR_REGISTERED:
        LOGGER.info("Prometheus collector already registered, skipping")
        return

    try:
        REGISTRY.register(LocustCollector(environment, runner))
        _COLLECTOR_REGISTERED = True
        LOGGER.info("Prometheus collector registered successfully")
    except ValueError as exc:
        if "duplicated" in str(exc) or "already exists" in str(exc):
            LOGGER.warning("Prometheus collector already registered: %s", exc)
            _COLLECTOR_REGISTERED = True
        else:
            LOGGER.warning("Prometheus collector registration skipped: %s", exc)
    except Exception as exc:
        LOGGER.warning("Prometheus collector registration failed: %s", exc)
