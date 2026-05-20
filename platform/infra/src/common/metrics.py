from prometheus_client import start_http_server, Counter, Gauge, Histogram, Summary
from config import config
import time
from typing import Optional

class MetricsCollector:
    def __init__(self, service_name: str):
        self.service_name = service_name
        self.metrics_port = config.monitoring.prometheus_port

        # Prediction metrics
        self.prediction_requests = Counter(
            f'{service_name}_prediction_requests_total',
            'Total number of prediction requests',
            ['model_version', 'status']
        )

        self.prediction_latency = Histogram(
            f'{service_name}_prediction_latency_seconds',
            'Prediction latency in seconds',
            ['model_version']
        )

        self.prediction_confidence = Gauge(
            f'{service_name}_prediction_confidence',
            'Average prediction confidence score',
            ['model_version']
        )

        # Model performance metrics
        self.model_accuracy = Gauge(
            f'{service_name}_model_accuracy',
            'Model accuracy score',
            ['model_version', 'test_set']
        )

        self.model_loss = Gauge(
            f'{service_name}_model_loss',
            'Model loss value',
            ['model_version', 'epoch']
        )

        # RL metrics
        self.rl_reward = Gauge(
            f'{service_name}_rl_reward',
            'Average reward per episode',
            ['agent_type']
        )

        self.rl_exploration_rate = Gauge(
            f'{service_name}_rl_exploration_rate',
            'Current exploration rate',
            ['agent_type']
        )

        # System metrics
        self.memory_usage = Gauge(
            f'{service_name}_memory_usage_bytes',
            'Memory usage in bytes'
        )

        self.cpu_usage = Gauge(
            f'{service_name}_cpu_usage_percent',
            'CPU usage percentage'
        )

        self.gpu_memory = Gauge(
            f'{service_name}_gpu_memory_used_mb',
            'GPU memory used in MB'
        )

        # A/B testing metrics
        self.ab_test_conversions = Counter(
            f'{service_name}_ab_test_conversions_total',
            'Number of conversions per variant',
            ['test_name', 'variant']
        )

        self.ab_test_impressions = Counter(
            f'{service_name}_ab_test_impressions_total',
            'Number of impressions per variant',
            ['test_name', 'variant']
        )

        # Start metrics server
        self.start()

    def start(self):
        """Start the metrics server."""
        start_http_server(self.metrics_port)
        print(f"Metrics server started on port {self.metrics_port}")

    def track_prediction(self, model_version: str, latency: float, confidence: float, status: str = 'success'):
        """Track a prediction request."""
        self.prediction_requests.labels(model_version=model_version, status=status).inc()
        self.prediction_latency.labels(model_version=model_version).observe(latency)
        self.prediction_confidence.labels(model_version=model_version).set(confidence)

    def track_model_performance(self, model_version: str, accuracy: float, loss: float, epoch: int):
        """Track model performance metrics."""
        self.model_accuracy.labels(model_version=model_version, test_set='validation').set(accuracy)
        self.model_loss.labels(model_version=model_version, epoch=epoch).set(loss)

    def track_rl_reward(self, agent_type: str, reward: float, exploration_rate: float):
        """Track reinforcement learning metrics."""
        self.rl_reward.labels(agent_type=agent_type).set(reward)
        self.rl_exploration_rate.labels(agent_type=agent_type).set(exploration_rate)

    def track_system_metrics(self, memory_usage: int, cpu_usage: float, gpu_memory: int):
        """Track system resource metrics."""
        self.memory_usage.set(memory_usage)
        self.cpu_usage.set(cpu_usage)
        self.gpu_memory.set(gpu_memory)

    def track_ab_test(self, test_name: str, variant: str, impression: bool = False, conversion: bool = False):
        """Track A/B test metrics."""
        if impression:
            self.ab_test_impressions.labels(test_name=test_name, variant=variant).inc()
        if conversion:
            self.ab_test_conversions.labels(test_name=test_name, variant=variant).inc()

# Global metrics collector
metrics = MetricsCollector('award-travel-engine')
