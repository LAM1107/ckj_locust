from datetime import datetime
from pathlib import Path

from locust import events
from locust.runners import LocalRunner, MasterRunner

from config.config_settings import LoadTestConfig
from read_utils.business_metrics import snapshot_metrics


def _should_write_report(environment):
    if not LoadTestConfig.ENABLE_METRICS_REPORT:
        return False

    runner = getattr(environment, "runner", None)
    return runner is None or isinstance(runner, (LocalRunner, MasterRunner))


def _format_read_write_ratio(read_count, write_count):
    if write_count == 0:
        return "0:0" if read_count == 0 else "read-only"
    return f"{read_count / write_count:.2f}:1"


@events.quitting.add_listener
def on_quitting(environment, **kwargs):
    if not _should_write_report(environment):
        return

    total_stats = environment.stats.total
    entries = environment.stats.entries
    business_metrics = snapshot_metrics(environment)
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = Path.cwd() / f"locust_metrics_{timestamp}.txt"

    flow_started = business_metrics["flow_started"]
    flow_succeeded = business_metrics["flow_succeeded"]
    flow_failed = business_metrics["flow_failed"]
    read_request_count = business_metrics["read_request_count"]
    write_request_count = business_metrics["write_request_count"]
    flow_success_rate = (flow_succeeded / flow_started * 100) if flow_started else 0.0

    try:
        with open(filename, "w", encoding="utf-8") as report:
            report.write("Locust performance report\n")
            report.write("=" * 80 + "\n\n")

            report.write("Run summary\n")
            report.write(f"Scenario mode: {LoadTestConfig.SCENARIO_MODE}\n")
            report.write(f"Total requests: {total_stats.num_requests}\n")
            report.write(f"Total failures: {total_stats.num_failures}\n")
            report.write(f"Failure rate: {total_stats.fail_ratio * 100:.2f}%\n")
            report.write(f"Average response time: {total_stats.avg_response_time:.2f} ms\n")
            report.write(f"Median response time: {total_stats.median_response_time:.2f} ms\n")
            report.write(f"Min response time: {total_stats.min_response_time or 0:.2f} ms\n")
            report.write(f"Max response time: {total_stats.max_response_time:.2f} ms\n")
            report.write(
                "P90 response time: "
                f"{total_stats.get_response_time_percentile(0.9):.2f} ms\n"
            )
            report.write(f"Requests per second: {total_stats.total_rps:.2f}\n")
            report.write(f"Failures per second: {total_stats.total_fail_per_sec:.2f}\n\n")

            report.write("Business metrics\n")
            # 这部分补充 Locust 的 HTTP 指标，展示场景级成功数和读写比例。
            report.write(f"Flow started: {flow_started}\n")
            report.write(f"Flow succeeded: {flow_succeeded}\n")
            report.write(f"Flow failed: {flow_failed}\n")
            report.write(f"Flow success rate: {flow_success_rate:.2f}%\n")
            report.write(f"Read requests: {read_request_count}\n")
            report.write(f"Write requests: {write_request_count}\n")
            report.write(
                "App-side read/write ratio: "
                f"{_format_read_write_ratio(read_request_count, write_request_count)}\n\n"
            )

            report.write("Per-endpoint stats\n")
            header = (
                f"{'Method':<8} {'Name':<60} {'Requests':>10} {'Failures':>10} "
                f"{'Fail%':>8} | {'Avg(ms)':>10} {'Median':>10} {'Min':>10} "
                f"{'Max':>10} {'P90':>10} | {'RPS':>10} {'Fail/s':>10}\n"
            )
            separator = "-" * 180 + "\n"
            report.write(header)
            report.write(separator)

            for key in entries:
                stat = entries[key]
                fail_rate = (stat.num_failures / stat.num_requests * 100) if stat.num_requests else 0
                report.write(
                    f"{stat.method:<8} {stat.name:<60} {stat.num_requests:>10} "
                    f"{stat.num_failures:>10} {fail_rate:>7.2f}% | "
                    f"{stat.avg_response_time:>10.2f} {stat.median_response_time:>10.2f} "
                    f"{stat.min_response_time or 0:>10.2f} {stat.max_response_time:>10.2f} "
                    f"{stat.get_response_time_percentile(0.9):>10.2f} | "
                    f"{stat.current_rps:>10.2f} {stat.current_fail_per_sec:>10.2f}\n"
                )

            report.write(separator)
            report.write(
                f"{'Aggregated':<8} {'Aggregated':<60} {total_stats.num_requests:>10} "
                f"{total_stats.num_failures:>10} {total_stats.fail_ratio * 100:>7.2f}% | "
                f"{total_stats.avg_response_time:>10.2f} {total_stats.median_response_time:>10.2f} "
                f"{total_stats.min_response_time or 0:>10.2f} {total_stats.max_response_time:>10.2f} "
                f"{total_stats.get_response_time_percentile(0.9):>10.2f} | "
                f"{total_stats.total_rps:>10.2f} {total_stats.total_fail_per_sec:>10.2f}\n"
            )

        print(f"Saved metrics report: {filename}")
    except Exception as exc:
        print(f"Failed to write metrics report: {exc}")
