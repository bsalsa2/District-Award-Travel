#!/usr/bin/env python3
"""
Metrics Collector for District Award Travel
Collects system, application, and business metrics for monitoring dashboard
"""

import os
import time
import socket
import logging
from datetime import datetime
from typing import Dict, Any

import psutil
import docker
from influxdb_client import InfluxDBClient, Point, WritePrecision
from influxdb_client.client.write_api import SYNCHRONOUS
from prometheus_client import start_http_server, Counter, Gauge, Histogram
from pythonjsonlogger import jsonlogger

# Configure logging
def setup_logging():
    logger = logging.getLogger('metrics_collector')
    logger.setLevel(logging.INFO)

    # JSON formatter for structured logging
    formatter = jsonlogger.JsonFormatter(
        '%(asctime)s %(levelname)s %(name)s %(message)s'
    )

    # Console handler
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(formatter)
    logger.addHandler(console_handler)

    return logger

logger = setup_logging()

# Metrics configuration
METRICS_PORT = int(os.getenv('METRICS_PORT', '9090'))
COLLECTOR_INTERVAL = int(os.getenv('COLLECTOR_INTERVAL', '30'))
HOSTNAME = socket.gethostname()

# InfluxDB configuration
INFLUXDB_URL = os.getenv('INFLUXDB_URL', 'http://influxdb:8086')
INFLUXDB_TOKEN = os.getenv('INFLUXDB_TOKEN', 'mytoken')
INFLUXDB_ORG = os.getenv('INFLUXDB_ORG', 'district-award-travel')
INFLUXDB_BUCKET = os.getenv('INFLUXDB_BUCKET', 'metrics')

# Initialize InfluxDB client
influx_client = InfluxDBClient(
    url=INFLUXDB_URL,
    token=INFLUXDB_TOKEN,
    org=INFLUXDB_ORG
)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

# Prometheus metrics for self-monitoring
METRICS_COLLECTED = Counter(
    'metrics_collected_total',
    'Total number of metrics collected',
    ['metric_type']
)

SYSTEM_CPU_USAGE = Gauge(
    'system_cpu_usage_percent',
    'System CPU usage percentage'
)

SYSTEM_MEMORY_USAGE = Gauge(
    'system_memory_usage_bytes',
    'System memory usage in bytes'
)

SYSTEM_DISK_USAGE = Gauge(
    'system_disk_usage_bytes',
    'System disk usage in bytes'
)

APP_RESPONSE_TIME = Histogram(
    'application_response_time_seconds',
    'Application response time in seconds',
    buckets=[0.1, 0.5, 1.0, 2.0, 5.0, 10.0]
)

TRAVEL_BOOKINGS = Counter(
    'travel_bookings_total',
    'Total number of travel bookings processed',
    ['booking_type', 'status']
)

AWARD_REDEMPTIONS = Counter(
    'award_redemptions_total',
    'Total number of award redemptions',
    ['program', 'tier']
)

class MetricsCollector:
    """Main metrics collection class"""

    def __init__(self):
        self.docker_client = docker.from_env()
        self.last_collection_time = time.time()

    def collect_system_metrics(self) -> Dict[str, Any]:
        """Collect system-level metrics"""
        metrics = {}

        # CPU usage
        cpu_usage = psutil.cpu_percent(interval=1)
        SYSTEM_CPU_USAGE.set(cpu_usage)
        metrics['cpu_usage_percent'] = cpu_usage

        # Memory usage
        memory = psutil.virtual_memory()
        SYSTEM_MEMORY_USAGE.set(memory.used)
        metrics['memory_usage_bytes'] = memory.used
        metrics['memory_total_bytes'] = memory.total
        metrics['memory_percent'] = memory.percent

        # Disk usage
        disk = psutil.disk_usage('/')
        SYSTEM_DISK_USAGE.set(disk.used)
        metrics['disk_usage_bytes'] = disk.used
        metrics['disk_total_bytes'] = disk.total
        metrics['disk_percent'] = disk.percent

        # Network stats
        net_io = psutil.net_io_counters()
        metrics['network_bytes_sent'] = net_io.bytes_sent
        metrics['network_bytes_recv'] = net_io.bytes_recv

        # System load
        load_avg = os.getloadavg()
        metrics['load_avg_1min'] = load_avg[0]
        metrics['load_avg_5min'] = load_avg[1]
        metrics['load_avg_15min'] = load_avg[2]

        METRICS_COLLECTED.labels(metric_type='system').inc()
        return metrics

    def collect_container_metrics(self) -> Dict[str, Any]:
        """Collect Docker container metrics"""
        metrics = {}

        try:
            containers = self.docker_client.containers.list()
            for container in containers:
                stats = container.stats(stream=False)
                container_name = container.name

                # Extract CPU usage
                cpu_delta = stats['cpu_stats']['cpu_usage']['total_usage'] - \
                           stats['precpu_stats']['cpu_usage']['total_usage']
                system_cpu_delta = stats['cpu_stats']['system_cpu_usage'] - \
                                  stats['precpu_stats']['system_cpu_usage']
                cpu_percent = (cpu_delta / system_cpu_delta) * 100.0 * \
                             len(stats['cpu_stats']['cpu_usage']['percpu_usage'])

                # Extract memory usage
                memory_usage = stats['memory_stats']['usage']
                memory_limit = stats['memory_stats']['limit']

                metrics[f'container_{container_name}_cpu_percent'] = cpu_percent
                metrics[f'container_{container_name}_memory_usage_bytes'] = memory_usage
                metrics[f'container_{container_name}_memory_limit_bytes'] = memory_limit

        except Exception as e:
            logger.error(f"Error collecting container metrics: {str(e)}")

        METRICS_COLLECTED.labels(metric_type='container').inc()
        return metrics

    def collect_application_metrics(self) -> Dict[str, Any]:
        """Collect application-specific metrics"""
        metrics = {}

        # Simulate application response time measurement
        start_time = time.time()
        time.sleep(0.1)  # Simulate work
        response_time = time.time() - start_time

        APP_RESPONSE_TIME.observe(response_time)
        metrics['application_response_time_seconds'] = response_time

        # Business metrics simulation
        # In a real implementation, these would come from your application
        travel_bookings = {
            'economy': {'booked': 15, 'cancelled': 2},
            'business': {'booked': 8, 'cancelled': 1},
            'first': {'booked': 3, 'cancelled': 0}
        }

        for booking_type, stats in travel_bookings.items():
            TRAVEL_BOOKINGS.labels(booking_type=booking_type, status='booked').inc(stats['booked'])
            TRAVEL_BOOKINGS.labels(booking_type=booking_type, status='cancelled').inc(stats['cancelled'])

        # Award redemption metrics
        award_redemptions = {
            'platinum': {'redemptions': 5, 'value': 15000},
            'gold': {'redemptions': 12, 'value': 8000},
            'silver': {'redemptions': 25, 'value': 3000}
        }

        for tier, stats in award_redemptions.items():
            AWARD_REDEMPTIONS.labels(program='district_awards', tier=tier).inc(stats['redemptions'])

        METRICS_COLLECTED.labels(metric_type='application').inc()
        return metrics

    def write_to_influxdb(self, metrics: Dict[str, Any], measurement: str):
        """Write metrics to InfluxDB"""
        try:
            point = Point(measurement) \
                .tag("host", HOSTNAME) \
                .time(datetime.utcnow(), WritePrecision.NS)

            for key, value in metrics.items():
                point.field(key, value)

            write_api.write(bucket=INFLUXDB_BUCKET, org=INFLUXDB_ORG, record=point)
            logger.info(f"Successfully wrote {measurement} metrics to InfluxDB")
        except Exception as e:
            logger.error(f"Error writing to InfluxDB: {str(e)}")

    def collect_and_store(self):
        """Main collection and storage method"""
        collection_start = time.time()

        try:
            logger.info("Starting metrics collection cycle")

            # Collect system metrics
            system_metrics = self.collect_system_metrics()
            self.write_to_influxdb(system_metrics, "system_metrics")

            # Collect container metrics
            container_metrics = self.collect_container_metrics()
            if container_metrics:
                self.write_to_influxdb(container_metrics, "container_metrics")

            # Collect application metrics
            app_metrics = self.collect_application_metrics()
            self.write_to_influxdb(app_metrics, "application_metrics")

            # Calculate collection duration
            collection_duration = time.time() - collection_start
            logger.info(f"Metrics collection completed in {collection_duration:.2f} seconds")

        except Exception as e:
            logger.error(f"Error during metrics collection: {str(e)}")

def main():
    """Main entry point"""
    logger.info("Starting District Award Travel Metrics Collector")

    # Start Prometheus metrics server
    start_http_server(METRICS_PORT)
    logger.info(f"Prometheus metrics server started on port {METRICS_PORT}")

    # Initialize collector
    collector = MetricsCollector()

    # Main collection loop
    while True:
        try:
            collector.collect_and_store()
        except KeyboardInterrupt:
            logger.info("Shutting down metrics collector...")
            break
        except Exception as e:
            logger.error(f"Unexpected error in collection loop: {str(e)}")

        # Sleep until next collection
        time.sleep(COLLECTOR_INTERVAL)

if __name__ == "__main__":
    main()
