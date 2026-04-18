from __future__ import annotations

from collections import Counter
from threading import Lock


def _escape_metric_label(value: str) -> str:
    return value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")


class ObservabilityRegistry:
    def __init__(self) -> None:
        self._lock = Lock()
        self._http_requests_total: Counter[tuple[str, str, str]] = Counter()
        self._http_request_duration_seconds_count: Counter[tuple[str, str]] = Counter()
        self._http_request_duration_seconds_sum: dict[tuple[str, str], float] = {}
        self._http_request_duration_seconds_bucket: Counter[tuple[str, str, str]] = Counter()
        self._http_error_responses_total: Counter[tuple[str, str]] = Counter()
        self._rate_limited_requests_total: Counter[str] = Counter()
        self._unhandled_exceptions_total: Counter[tuple[str, str]] = Counter()
        self._dependency_health_status: dict[str, int] = {}
        self._duration_buckets = (0.005, 0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1.0, 2.5, 5.0, 10.0)

    def reset(self) -> None:
        with self._lock:
            self._http_requests_total.clear()
            self._http_request_duration_seconds_count.clear()
            self._http_request_duration_seconds_sum.clear()
            self._http_request_duration_seconds_bucket.clear()
            self._http_error_responses_total.clear()
            self._rate_limited_requests_total.clear()
            self._unhandled_exceptions_total.clear()
            self._dependency_health_status.clear()

    def record_request(self, *, method: str, path: str, status_code: int, duration_seconds: float) -> None:
        status_code_label = str(status_code)
        key = (method, path, status_code_label)
        duration_key = (method, path)

        with self._lock:
            self._http_requests_total[key] += 1
            self._http_request_duration_seconds_count[duration_key] += 1
            self._http_request_duration_seconds_sum[duration_key] = (
                self._http_request_duration_seconds_sum.get(duration_key, 0.0) + duration_seconds
            )
            for bucket in self._duration_buckets:
                if duration_seconds <= bucket:
                    self._http_request_duration_seconds_bucket[(method, path, str(bucket))] += 1
            self._http_request_duration_seconds_bucket[(method, path, "+Inf")] += 1
            if status_code >= 400:
                self._http_error_responses_total[(path, status_code_label)] += 1

    def record_rate_limited_request(self, *, path: str) -> None:
        with self._lock:
            self._rate_limited_requests_total[path] += 1

    def record_unhandled_exception(self, *, path: str, error_type: str) -> None:
        with self._lock:
            self._unhandled_exceptions_total[(path, error_type)] += 1

    def set_dependency_health(self, *, component: str, is_healthy: bool) -> None:
        with self._lock:
            self._dependency_health_status[component] = 1 if is_healthy else 0

    def render_prometheus(self) -> str:
        lines: list[str] = []

        def emit_help_and_type(name: str, help_text: str, metric_type: str) -> None:
            lines.append(f"# HELP {name} {help_text}")
            lines.append(f"# TYPE {name} {metric_type}")

        with self._lock:
            emit_help_and_type(
                "field_service_http_requests_total",
                "Total HTTP requests processed by the API.",
                "counter",
            )
            for (method, path, status_code), count in sorted(self._http_requests_total.items()):
                lines.append(
                    'field_service_http_requests_total{method="%s",path="%s",status_code="%s"} %s'
                    % (
                        _escape_metric_label(method),
                        _escape_metric_label(path),
                        _escape_metric_label(status_code),
                        count,
                    )
                )

            emit_help_and_type(
                "field_service_http_request_duration_seconds",
                "HTTP request duration in seconds.",
                "histogram",
            )
            duration_keys = sorted(self._http_request_duration_seconds_count.keys())
            for method, path in duration_keys:
                for bucket in [*(str(value) for value in self._duration_buckets), "+Inf"]:
                    bucket_count = self._http_request_duration_seconds_bucket.get((method, path, bucket), 0)
                    lines.append(
                        'field_service_http_request_duration_seconds_bucket{method="%s",path="%s",le="%s"} %s'
                        % (
                            _escape_metric_label(method),
                            _escape_metric_label(path),
                            _escape_metric_label(bucket),
                            bucket_count,
                        )
                    )
                lines.append(
                    'field_service_http_request_duration_seconds_count{method="%s",path="%s"} %s'
                    % (
                        _escape_metric_label(method),
                        _escape_metric_label(path),
                        self._http_request_duration_seconds_count[(method, path)],
                    )
                )
                lines.append(
                    'field_service_http_request_duration_seconds_sum{method="%s",path="%s"} %.6f'
                    % (
                        _escape_metric_label(method),
                        _escape_metric_label(path),
                        self._http_request_duration_seconds_sum[(method, path)],
                    )
                )

            emit_help_and_type(
                "field_service_http_error_responses_total",
                "Total HTTP error responses returned by the API.",
                "counter",
            )
            for (path, status_code), count in sorted(self._http_error_responses_total.items()):
                lines.append(
                    'field_service_http_error_responses_total{path="%s",status_code="%s"} %s'
                    % (
                        _escape_metric_label(path),
                        _escape_metric_label(status_code),
                        count,
                    )
                )

            emit_help_and_type(
                "field_service_rate_limited_requests_total",
                "Total requests rejected by rate limiting.",
                "counter",
            )
            for path, count in sorted(self._rate_limited_requests_total.items()):
                lines.append(
                    'field_service_rate_limited_requests_total{path="%s"} %s'
                    % (
                        _escape_metric_label(path),
                        count,
                    )
                )

            emit_help_and_type(
                "field_service_unhandled_exceptions_total",
                "Total unhandled exceptions raised by the API.",
                "counter",
            )
            for (path, error_type), count in sorted(self._unhandled_exceptions_total.items()):
                lines.append(
                    'field_service_unhandled_exceptions_total{path="%s",error_type="%s"} %s'
                    % (
                        _escape_metric_label(path),
                        _escape_metric_label(error_type),
                        count,
                    )
                )

            emit_help_and_type(
                "field_service_dependency_health_status",
                "Last observed dependency health status where 1 means healthy and 0 means unhealthy.",
                "gauge",
            )
            for component, value in sorted(self._dependency_health_status.items()):
                lines.append(
                    'field_service_dependency_health_status{component="%s"} %s'
                    % (_escape_metric_label(component), value)
                )

        return "\n".join(lines) + "\n"


observability_registry = ObservabilityRegistry()
