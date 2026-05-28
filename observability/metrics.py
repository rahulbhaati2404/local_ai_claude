from collections import defaultdict
from core.logger import logger

class MetricsCollector:

    def __init__(self):
        self.metrics = defaultdict(list)

    def record(self, metric_name: str, value):
        self.metrics[metric_name].append(value)
        logger.info(f"[METRIC] {metric_name}={value}")

    def summary(self):
        report = {}

        for key, values in self.metrics.items():
            if not values:
                continue

            numeric_values = [
                v for v in values 
                if isinstance(v, (int, float)) and not isinstance(v, bool)
            ]

            if not numeric_values:
                report[key] = {
                    "count": len(values),
                    "last_recorded_value": values[-1]
                }
                continue

            report[key] = {
                "count": len(values),
                "avg": sum(numeric_values) / len(numeric_values),
                "max": max(numeric_values),
                "min": min(numeric_values)
            }

        return report

metrics_collector = MetricsCollector()