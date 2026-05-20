#!/usr/bin/env python3
"""
District Award Travel Monitoring System
Tracks API performance, search analytics, error rates, and business metrics
"""

import os
import sys
import time
import json
import logging
import smtplib
from datetime import datetime, timedelta
from email.mime.text import MIMEText
from typing import Dict, List, Any, Optional
import psycopg2
import psycopg2.extras
import requests
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import schedule

# Configuration
CONFIG = {
    "db": {
        "host": os.getenv("DB_HOST", "localhost"),
        "port": int(os.getenv("DB_PORT", "5432")),
        "name": os.getenv("DB_NAME", "district_award"),
        "user": os.getenv("DB_USER", "travel_admin"),
        "password": os.getenv("DB_PASSWORD", "secure_password"),
    },
    "api_endpoints": {
        "search": os.getenv("SEARCH_API", "http://localhost:8000/api/search"),
        "bookings": os.getenv("BOOKINGS_API", "http://localhost:8000/api/bookings"),
        "awards": os.getenv("AWARDS_API", "http://localhost:8000/api/awards"),
    },
    "alerts": {
        "email_from": os.getenv("ALERT_EMAIL_FROM", "alerts@districtaward.com"),
        "email_to": os.getenv("ALERT_EMAIL_TO", "engineering@districtaward.com"),
        "smtp_host": os.getenv("SMTP_HOST", "smtp.gmail.com"),
        "smtp_port": int(os.getenv("SMTP_PORT", "587")),
        "smtp_user": os.getenv("SMTP_USER", "alerts@districtaward.com"),
        "smtp_password": os.getenv("SMTP_PASSWORD", "email_password"),
    },
    "metrics": {
        "port": int(os.getenv("METRICS_PORT", "9090")),
        "interval": int(os.getenv("METRICS_INTERVAL", "30")),
    },
}

# Metrics
METRICS = {
    "api_response_time": Histogram(
        "api_response_time_seconds",
        "API response time in seconds",
        ["endpoint"],
    ),
    "search_throughput": Counter(
        "search_throughput_total",
        "Total number of searches performed",
        ["status"],
    ),
    "error_rate": Counter(
        "error_rate_total",
        "Total number of errors encountered",
        ["type"],
    ),
    "client_activity": Counter(
        "client_activity_total",
        "Client activity metrics",
        ["action", "client_type"],
    ),
    "revenue": Gauge(
        "revenue_usd",
        "Revenue in USD",
    ),
    "award_deals_found": Counter(
        "award_deals_found_total",
        "Number of exceptional award deals found",
    ),
}

# Logging setup
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    handlers=[
        logging.FileHandler("/var/log/district_award/monitor.log"),
        logging.StreamHandler(),
    ],
)
logger = logging.getLogger("DistrictAwardMonitor")

class DatabaseMonitor:
    """Monitor PostgreSQL database performance and health"""

    def __init__(self):
        self.conn = None

    def connect(self):
        """Establish database connection"""
        try:
            self.conn = psycopg2.connect(
                host=CONFIG["db"]["host"],
                port=CONFIG["db"]["port"],
                dbname=CONFIG["db"]["name"],
                user=CONFIG["db"]["user"],
                password=CONFIG["db"]["password"],
                connect_timeout=5,
            )
            logger.info("Successfully connected to database")
            return True
        except Exception as e:
            logger.error(f"Database connection failed: {e}")
            METRICS["error_rate"].labels(type="database").inc()
            return False

    def get_db_metrics(self) -> Dict[str, Any]:
        """Collect database performance metrics"""
        if not self.conn:
            if not self.connect():
                return {}

        metrics = {
            "active_connections": 0,
            "query_latency": 0,
            "cache_hit_ratio": 0,
            "locks_waiting": 0,
        }

        try:
            with self.conn.cursor() as cursor:
                # Active connections
                cursor.execute("SELECT count(*) FROM pg_stat_activity;")
                metrics["active_connections"] = cursor.fetchone()[0]

                # Query latency (95th percentile)
                cursor.execute("""
                    SELECT percentile_cont(0.95) WITHIN GROUP (ORDER BY total_time) as latency
                    FROM pg_stat_statements;
                """)
                result = cursor.fetchone()
                metrics["query_latency"] = result[0] if result[0] else 0

                # Cache hit ratio
                cursor.execute("""
                    SELECT sum(blks_hit) / (sum(blks_hit) + sum(blks_read))::float
                    FROM pg_stat_database;
                """)
                result = cursor.fetchone()
                metrics["cache_hit_ratio"] = result[0] if result[0] else 0

                # Locks waiting
                cursor.execute("""
                    SELECT count(*) FROM pg_locks l
                    JOIN pg_class c ON l.relation = c.oid
                    WHERE mode = 'ExclusiveLock' AND granted = false;
                """)
                metrics["locks_waiting"] = cursor.fetchone()[0]

        except Exception as e:
            logger.error(f"Failed to collect database metrics: {e}")
            METRICS["error_rate"].labels(type="database_query").inc()

        return metrics

class APIMonitor:
    """Monitor API endpoints and track performance"""

    def __init__(self):
        self.session = requests.Session()
        self.session.headers.update({
            "User-Agent": "DistrictAward-Monitor/1.0",
            "Accept": "application/json",
        })

    def check_endpoint(self, endpoint: str, timeout: int = 5) -> Dict[str, Any]:
        """Check API endpoint health and performance"""
        start_time = time.time()
        status = "unknown"
        response_time = 0
        error = None

        try:
            response = self.session.get(endpoint, timeout=timeout)
            response_time = time.time() - start_time

            if response.status_code == 200:
                status = "success"
                METRICS["api_response_time"].labels(endpoint=endpoint).observe(response_time)
            else:
                status = "error"
                error = f"HTTP {response.status_code}"
                METRICS["error_rate"].labels(type="api_http").inc()

        except requests.exceptions.RequestException as e:
            response_time = time.time() - start_time
            status = "error"
            error = str(e)
            METRICS["error_rate"].labels(type="api_request").inc()

        return {
            "endpoint": endpoint,
            "status": status,
            "response_time": response_time,
            "timestamp": datetime.utcnow().isoformat(),
            "error": error,
        }

class SearchAnalytics:
    """Track search pipeline performance and user behavior"""

    def __init__(self, db_monitor: DatabaseMonitor):
        self.db = db_monitor

    def track_search(self, query: str, results_count: int, client_type: str = "web") -> bool:
        """Track a search operation"""
        try:
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    INSERT INTO search_analytics
                    (query, results_count, client_type, timestamp)
                    VALUES (%s, %s, %s, NOW())
                """, (query, results_count, client_type))

                self.db.conn.commit()
                METRICS["search_throughput"].labels(status="success").inc()
                METRICS["client_activity"].labels(action="search", client_type=client_type).inc()
                return True
        except Exception as e:
            logger.error(f"Failed to track search: {e}")
            METRICS["error_rate"].labels(type="search_tracking").inc()
            METRICS["search_throughput"].labels(status="failed").inc()
            return False

    def get_search_metrics(self, hours: int = 24) -> Dict[str, Any]:
        """Get search analytics for dashboard"""
        if not self.db.conn:
            if not self.db.connect():
                return {}

        metrics = {
            "total_searches": 0,
            "avg_results": 0,
            "top_queries": [],
            "hourly_volume": [],
        }

        try:
            with self.db.conn.cursor() as cursor:
                # Total searches
                cursor.execute("""
                    SELECT COUNT(*) FROM search_analytics
                    WHERE timestamp >= NOW() - INTERVAL '%s hours'
                """, (hours,))
                metrics["total_searches"] = cursor.fetchone()[0]

                # Average results
                cursor.execute("""
                    SELECT AVG(results_count) FROM search_analytics
                    WHERE timestamp >= NOW() - INTERVAL '%s hours'
                """, (hours,))
                result = cursor.fetchone()
                metrics["avg_results"] = result[0] if result[0] else 0

                # Top queries
                cursor.execute("""
                    SELECT query, COUNT(*) as count
                    FROM search_analytics
                    WHERE timestamp >= NOW() - INTERVAL '%s hours'
                    GROUP BY query
                    ORDER BY count DESC
                    LIMIT 10
                """, (hours,))
                metrics["top_queries"] = [{"query": row[0], "count": row[1]} for row in cursor.fetchall()]

                # Hourly volume
                cursor.execute("""
                    SELECT DATE_TRUNC('hour', timestamp) as hour,
                           COUNT(*) as count
                    FROM search_analytics
                    WHERE timestamp >= NOW() - INTERVAL '%s hours'
                    GROUP BY DATE_TRUNC('hour', timestamp)
                    ORDER BY hour
                """, (hours,))
                metrics["hourly_volume"] = [{"hour": row[0].isoformat(), "count": row[1]} for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get search metrics: {e}")
            METRICS["error_rate"].labels(type="search_analytics").inc()

        return metrics

class BusinessIntelligence:
    """Track business metrics like revenue, client growth, and award programs"""

    def __init__(self, db_monitor: DatabaseMonitor):
        self.db = db_monitor

    def get_revenue_metrics(self, months: int = 12) -> Dict[str, Any]:
        """Get revenue data for bar chart"""
        if not self.db.conn:
            if not self.db.connect():
                return {}

        metrics = {
            "labels": [],
            "data": [],
        }

        try:
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DATE_TRUNC('month', created_at) as month,
                           SUM(amount) as revenue
                    FROM bookings
                    WHERE created_at >= DATE_TRUNC('month', NOW()) - INTERVAL '%s months'
                    GROUP BY DATE_TRUNC('month', created_at)
                    ORDER BY month
                """, (months,))

                rows = cursor.fetchall()
                for row in rows:
                    metrics["labels"].append(row[0].strftime("%Y-%m"))
                    metrics["data"].append(float(row[1]))

        except Exception as e:
            logger.error(f"Failed to get revenue metrics: {e}")
            METRICS["error_rate"].labels(type="revenue_metrics").inc()

        return metrics

    def get_client_growth(self, months: int = 12) -> Dict[str, Any]:
        """Get client growth data for line chart"""
        if not self.db.conn:
            if not self.db.connect():
                return {}

        metrics = {
            "labels": [],
            "data": [],
        }

        try:
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT DATE_TRUNC('month', created_at) as month,
                           COUNT(*) as new_clients
                    FROM clients
                    WHERE created_at >= DATE_TRUNC('month', NOW()) - INTERVAL '%s months'
                    GROUP BY DATE_TRUNC('month', created_at)
                    ORDER BY month
                """, (months,))

                rows = cursor.fetchall()
                for row in rows:
                    metrics["labels"].append(row[0].strftime("%Y-%m"))
                    metrics["data"].append(row[1])

        except Exception as e:
            logger.error(f"Failed to get client growth: {e}")
            METRICS["error_rate"].labels(type="client_growth").inc()

        return metrics

    def get_top_routes(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get top searched routes"""
        if not self.db.conn:
            if not self.db.connect():
                return []

        try:
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT departure, destination, COUNT(*) as searches
                    FROM search_analytics
                    WHERE timestamp >= NOW() - INTERVAL '30 days'
                    GROUP BY departure, destination
                    ORDER BY searches DESC
                    LIMIT %s
                """, (limit,))

                return [{"departure": row[0], "destination": row[1], "searches": row[2]} for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get top routes: {e}")
            METRICS["error_rate"].labels(type="top_routes").inc()
            return []

    def get_award_program_performance(self, limit: int = 10) -> List[Dict[str, Any]]:
        """Get best performing award programs"""
        if not self.db.conn:
            if not self.db.connect():
                return []

        try:
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT program_name, COUNT(*) as bookings,
                           SUM(amount) as revenue
                    FROM bookings
                    WHERE award_program IS NOT NULL
                    AND created_at >= NOW() - INTERVAL '90 days'
                    GROUP BY program_name
                    ORDER BY bookings DESC
                    LIMIT %s
                """, (limit,))

                return [{
                    "program": row[0],
                    "bookings": row[1],
                    "revenue": float(row[2]),
                } for row in cursor.fetchall()]

        except Exception as e:
            logger.error(f"Failed to get award program performance: {e}")
            METRICS["error_rate"].labels(type="award_performance").inc()
            return []

    def get_engineer_productivity(self, days: int = 7) -> Dict[str, Any]:
        """Get engineer task completion metrics"""
        if not self.db.conn:
            if not self.db.connect():
                return {}

        metrics = {
            "labels": [],
            "data": [],
        }

        try:
            with self.db.conn.cursor() as cursor:
                cursor.execute("""
                    SELECT engineer, COUNT(*) as tasks_completed
                    FROM tasks
                    WHERE completed_at >= NOW() - INTERVAL '%s days'
                    AND status = 'completed'
                    GROUP BY engineer
                    ORDER BY tasks_completed DESC
                """, (days,))

                rows = cursor.fetchall()
                for row in rows:
                    metrics["labels"].append(row[0])
                    metrics["data"].append(row[1])

        except Exception as e:
            logger.error(f"Failed to get engineer productivity: {e}")
            METRICS["error_rate"].labels(type="engineer_productivity").inc()

        return metrics

class AlertSystem:
    """Send alerts for critical issues and exceptional deals"""

    def __init__(self):
        self.smtp_config = CONFIG["alerts"]

    def send_email_alert(self, subject: str, message: str, is_html: bool = False):
        """Send email alert"""
        try:
            msg = MIMEText(message, "html" if is_html else "plain")
            msg["Subject"] = f"[District Award Alert] {subject}"
            msg["From"] = self.smtp_config["email_from"]
            msg["To"] = self.smtp_config["email_to"]

            with smtplib.SMTP(
                self.smtp_config["smtp_host"],
                self.smtp_config["smtp_port"]
            ) as server:
                server.starttls()
                server.login(
                    self.smtp_config["smtp_user"],
                    self.smtp_config["smtp_password"]
                )
                server.send_message(msg)

            logger.info(f"Alert sent: {subject}")
            return True
        except Exception as e:
            logger.error(f"Failed to send alert: {e}")
            return False

    def check_for_exceptional_deals(self):
        """Check for exceptional award deals and alert if found"""
        if not self.db.conn:
            if not self.db.connect():
                return False

        try:
            with self.db.conn.cursor() as cursor:
                # Check for deals with > 50% discount
                cursor.execute("""
                    SELECT
                        award_program,
                        departure,
                        destination,
                        original_price,
                        award_price,
                        (1 - (award_price / original_price)) * 100 as discount_percentage,
                        created_at
                    FROM bookings
                    WHERE award_program IS NOT NULL
                    AND (1 - (award_price / original_price)) > 0.5
                    AND created_at >= NOW() - INTERVAL '24 hours'
                    ORDER BY discount_percentage DESC
                    LIMIT 5
                """)

                deals = cursor.fetchall()
                if deals:
                    message = "<h2>Exceptional Award Deals Found!</h2>"
                    message += f"<p>Found {len(deals)} exceptional deals in the last 24 hours:</p>"
                    message += "<table border='1' cellpadding='5'><tr><th>Program</th><th>Route</th><th>Original</th><th>Award</th><th>Discount</th><th>Time</th></tr>"

                    for deal in deals:
                        program, departure, destination, original, award, discount, created = deal
                        message += f"""
                        <tr>
                            <td>{program}</td>
                            <td>{departure} → {destination}</td>
                            <td>${original:,.2f}</td>
                            <td>${award:,.2f}</td>
                            <td>{discount:.1f}%</td>
                            <td>{created}</td>
                        </tr>
                        """

                    message += "</table>"
                    message += "<p><a href='https://admin.districtaward.com/analytics'>View in Analytics Dashboard</a></p>"

                    self.send_email_alert(
                        "Exceptional Award Deals Detected",
                        message,
                        is_html=True
                    )
                    METRICS["award_deals_found"].inc(len(deals))
                    return True

        except Exception as e:
            logger.error(f"Failed to check for exceptional deals: {e}")
            METRICS["error_rate"].labels(type="deal_alert").inc()

        return False

    def check_system_health(self, api_monitor: APIMonitor, db_monitor: DatabaseMonitor):
        """Check overall system health and send alerts if issues detected"""
        issues = []

        # Check API endpoints
        for endpoint_name, endpoint_url in CONFIG["api_endpoints"].items():
            health = api_monitor.check_endpoint(endpoint_url)
            if health["status"] != "success":
                issues.append(f"API Endpoint {endpoint_name} is down: {health['error']}")

        # Check database
        db_metrics = db_monitor.get_db_metrics()
        if db_metrics.get("active_connections", 0) > 100:
            issues.append(f"High database connections: {db_metrics['active_connections']}")
        if db_metrics.get("locks_waiting", 0) > 10:
            issues.append(f"High database locks waiting: {db_metrics['locks_waiting']}")

        if issues:
            subject = f"System Health Alert - {len(issues)} issues detected"
            message = "<h2>System Health Issues Detected</h2>"
            message += "<ul>"
            for issue in issues:
                message += f"<li>{issue}</li>"
            message += "</ul>"
            message += "<p><a href='https://status.districtaward.com'>View Status Page</a></p>"

            self.send_email_alert(subject, message, is_html=True)
            return False

        return True

class MonitorSystem:
    """Main monitoring system that orchestrates all components"""

    def __init__(self):
        self.db_monitor = DatabaseMonitor()
        self.api_monitor = APIMonitor()
        self.search_analytics = SearchAnalytics(self.db_monitor)
        self.business_intel = BusinessIntelligence(self.db_monitor)
        self.alert_system = AlertSystem()

        # Ensure database connection
        self.db_monitor.connect()

        # Start metrics server
        start_http_server(CONFIG["metrics"]["port"])
        logger.info(f"Metrics server started on port {CONFIG['metrics']['port']}")

    def run_checks(self):
        """Run all monitoring checks"""
        logger.info("Starting monitoring checks...")

        # Check API endpoints
        for name, endpoint in CONFIG["api_endpoints"].items():
            health = self.api_monitor.check_endpoint(endpoint)
            logger.info(f"API {name} health: {health['status']} in {health['response_time']:.3f}s")

        # Check database
        db_metrics = self.db_monitor.get_db_metrics()
        logger.info(f"Database metrics: {db_metrics}")

        # Check for exceptional deals
        self.alert_system.check_for_exceptional_deals()

        # Check system health
        self.alert_system.check_system_health(self.api_monitor, self.db_monitor)

        logger.info("Monitoring checks completed")

    def generate_dashboard_data(self) -> Dict[str, Any]:
        """Generate complete dashboard data"""
        return {
            "revenue": self.business_intel.get_revenue_metrics(months=12),
            "client_growth": self.business_intel.get_client_growth(months=12),
            "top_routes": self.business_intel.get_top_routes(limit=10),
            "award_programs": self.business_intel.get_award_program_performance(limit=10),
            "engineer_productivity": self.business_intel.get_engineer_productivity(days=7),
            "search_metrics": self.search_analytics.get_search_metrics(hours=24),
            "db_metrics": self.db_monitor.get_db_metrics(),
            "timestamp": datetime.utcnow().isoformat(),
        }

    def save_dashboard_data(self):
        """Save dashboard data for the frontend"""
        data = self.generate_dashboard_data()
        dashboard_path = "/var/www/district-award/public/admin/analytics/data.json"

        try:
            os.makedirs(os.path.dirname(dashboard_path), exist_ok=True)
            with open(dashboard_path, "w") as f:
                json.dump(data, f, indent=2)
            logger.info(f"Dashboard data saved to {dashboard_path}")
        except Exception as e:
            logger.error(f"Failed to save dashboard data: {e}")
            METRICS["error_rate"].labels(type="dashboard_save").inc()

def main():
    """Main entry point"""
    monitor = MonitorSystem()

    # Initial run
    monitor.run_checks()
    monitor.save_dashboard_data()

    # Schedule periodic checks
    schedule.every(CONFIG["metrics"]["interval"]).minutes.do(monitor.run_checks)
    schedule.every(15).minutes.do(monitor.save_dashboard_data)
    schedule.every().hour.do(monitor.alert_system.check_for_exceptional_deals)

    logger.info("Monitoring system started. Press Ctrl+C to exit.")

    try:
        while True:
            schedule.run_pending()
            time.sleep(60)
    except KeyboardInterrupt:
        logger.info("Monitoring system stopped")

if __name__ == "__main__":
    main()
