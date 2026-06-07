#!/usr/bin/env python3
"""
Award Space Monitoring System for District Award Travel
Monitors award space across major airlines and alerts on changes
"""

import os
import sys
import time
import sqlite3
import json
import logging
import requests
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from prometheus_client import start_http_server, Counter, Gauge, Histogram
import threading
import hashlib
from concurrent.futures import ThreadPoolExecutor, as_completed

# Configuration
CONFIG = {
    "database_path": "/data/award_monitoring.db",
    "check_interval": 300,  # 5 minutes
    "prometheus_port": 9090,
    "log_level": logging.INFO,
    "airlines": {
        "AA": {"name": "American Airlines", "api": "https://api.aa.com/award-search"},
        "DL": {"name": "Delta Air Lines", "api": "https://api.delta.com/award-search"},
        "UA": {"name": "United Airlines", "api": "https://api.united.com/award-search"},
        "BA": {"name": "British Airways", "api": "https://api.ba.com/award-search"},
        "EK": {"name": "Emirates", "api": "https://api.emirates.com/award-search"},
        "JL": {"name": "Japan Airlines", "api": "https://api.jal.com/award-search"},
        "LH": {"name": "Lufthansa", "api": "https://api.lufthansa.com/award-search"},
        "QF": {"name": "Qantas", "api": "https://api.qantas.com/award-search"},
    },
    "routes": [
        {"origin": "JFK", "destination": "LHR", "class": "business"},
        {"origin": "LAX", "destination": "NRT", "class": "business"},
        {"origin": "SFO", "destination": "HKG", "class": "first"},
        {"origin": "DFW", "destination": "CDG", "class": "business"},
        {"origin": "ORD", "destination": "FRA", "class": "business"},
    ],
    "alert_threshold": 2,  # Alert after 2 consecutive changes
}

# Metrics
METRICS = {
    "checks_total": Counter(
        "award_space_checks_total",
        "Total number of award space checks performed"
    ),
    "changes_detected": Counter(
        "award_space_changes_total",
        "Total number of award space changes detected",
        ["airline", "route", "class"]
    ),
    "current_availability": Gauge(
        "award_space_current_availability",
        "Current award space availability (1=available, 0=not available)",
        ["airline", "route", "class"]
    ),
    "check_duration_seconds": Histogram(
        "award_space_check_duration_seconds",
        "Duration of award space checks in seconds",
        buckets=[1.0, 2.5, 5.0, 10.0, 15.0, 30.0]
    ),
    "alerts_triggered": Counter(
        "award_space_alerts_total",
        "Total number of alerts triggered",
        ["airline", "route", "class"]
    ),
}

@dataclass
class AwardSpace:
    airline: str
    origin: str
    destination: str
    cabin_class: str
    available: bool
    seats: int
    last_updated: datetime
    check_hash: str

class AwardMonitoringSystem:
    def __init__(self, config: Dict):
        self.config = config
        self.logger = self._setup_logging()
        self.db_conn = None
        self._init_database()
        self.alert_state = {}  # airline_route_class -> consecutive_changes

        # Initialize Prometheus metrics
        start_http_server(config["prometheus_port"])
        self.logger.info(f"Prometheus metrics server started on port {config['prometheus_port']}")

    def _setup_logging(self) -> logging.Logger:
        """Setup logging configuration"""
        logging.basicConfig(
            level=self.config["log_level"],
            format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            handlers=[
                logging.StreamHandler(sys.stdout),
                logging.FileHandler('/var/log/award_monitoring.log')
            ]
        )
        return logging.getLogger("AwardMonitoring")

    def _init_database(self) -> None:
        """Initialize SQLite database"""
        os.makedirs(os.path.dirname(self.config["database_path"]), exist_ok=True)

        self.db_conn = sqlite3.connect(self.config["database_path"])
        cursor = self.db_conn.cursor()

        # Create tables
        cursor.execute("""
        CREATE TABLE IF NOT EXISTS award_space (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            airline TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            cabin_class TEXT NOT NULL,
            available BOOLEAN NOT NULL,
            seats INTEGER NOT NULL,
            last_updated TIMESTAMP NOT NULL,
            check_hash TEXT NOT NULL,
            UNIQUE(airline, origin, destination, cabin_class, check_hash)
        )
        """)

        cursor.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            airline TEXT NOT NULL,
            origin TEXT NOT NULL,
            destination TEXT NOT NULL,
            cabin_class TEXT NOT NULL,
            alert_type TEXT NOT NULL,
            message TEXT NOT NULL,
            triggered_at TIMESTAMP NOT NULL,
            resolved_at TIMESTAMP NULL
        )
        """)

        cursor.execute("""
        CREATE INDEX IF NOT EXISTS idx_award_space_airline_route
        ON award_space(airline, origin, destination, cabin_class)
        """)

        self.db_conn.commit()
        self.logger.info("Database initialized successfully")

    def _get_award_space_from_api(self, airline: str, route: Dict) -> Optional[AwardSpace]:
        """
        Simulate API call to get award space for a specific airline and route
        In production, this would call actual airline APIs with proper authentication
        """
        try:
            # Simulate API delay
            time.sleep(0.5)

            # Simulate realistic award space data
            origin = route["origin"]
            destination = route["destination"]
            cabin_class = route["class"]

            # Generate deterministic but changing availability
            seed = hashlib.md5(f"{airline}{origin}{destination}{cabin_class}{int(time.time() / 300)}".encode()).hexdigest()

            # Convert hash to availability (changes every 5 minutes)
            available = int(seed, 16) % 10 > 2  # 70% availability
            seats = (int(seed[:8], 16) % 20) + 1  # 1-20 seats

            return AwardSpace(
                airline=airline,
                origin=origin,
                destination=destination,
                cabin_class=cabin_class,
                available=available,
                seats=seats,
                last_updated=datetime.utcnow(),
                check_hash=seed
            )

        except Exception as e:
            self.logger.error(f"Error fetching award space for {airline} {route}: {str(e)}")
            return None

    def _store_award_space(self, award_space: AwardSpace) -> bool:
        """Store award space data in database"""
        try:
            cursor = self.db_conn.cursor()

            cursor.execute("""
            INSERT OR IGNORE INTO award_space
            (airline, origin, destination, cabin_class, available, seats, last_updated, check_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                award_space.airline,
                award_space.origin,
                award_space.destination,
                award_space.cabin_class,
                award_space.available,
                award_space.seats,
                award_space.last_updated.isoformat(),
                award_space.check_hash
            ))

            self.db_conn.commit()
            return cursor.rowcount > 0

        except Exception as e:
            self.logger.error(f"Error storing award space: {str(e)}")
            return False

    def _check_for_changes(self, airline: str, route: Dict) -> Optional[Tuple[bool, int]]:
        """
        Check if award space has changed from previous check
        Returns: (has_changed, previous_seats)
        """
        cursor = self.db_conn.cursor()

        # Get most recent record for this airline/route/class
        cursor.execute("""
        SELECT available, seats, check_hash
        FROM award_space
        WHERE airline = ? AND origin = ? AND destination = ? AND cabin_class = ?
        ORDER BY last_updated DESC
        LIMIT 1
        """, (
            airline,
            route["origin"],
            route["destination"],
            route["class"]
        ))

        result = cursor.fetchone()

        if result:
            prev_available, prev_seats, prev_hash = result

            # Simulate new check
            new_award_space = self._get_award_space_from_api(airline, route)
            if not new_award_space:
                return None

            # Check if availability changed
            availability_changed = new_award_space.available != prev_available
            seats_changed = new_award_space.seats != prev_seats

            if availability_changed or seats_changed:
                self.logger.info(
                    f"Award space change detected for {airline} {route['origin']}-{route['destination']} "
                    f"{route['class']}: {prev_available}->{new_award_space.available}, "
                    f"seats {prev_seats}->{new_award_space.seats}"
                )
                return True, prev_seats

        return False, 0

    def _trigger_alert(self, airline: str, route: Dict, message: str) -> None:
        """Trigger an alert and store in database"""
        alert_key = f"{airline}_{route['origin']}_{route['destination']}_{route['class']}"

        # Update alert state
        if alert_key not in self.alert_state:
            self.alert_state[alert_key] = 0

        self.alert_state[alert_key] += 1

        # Only trigger alert after threshold
        if self.alert_state[alert_key] >= self.config["alert_threshold"]:
            alert_type = "AVAILABILITY_CHANGE" if self.alert_state[alert_key] == self.config["alert_threshold"] else "PERSISTENT_CHANGE"

            cursor = self.db_conn.cursor()
            cursor.execute("""
            INSERT INTO alerts
            (airline, origin, destination, cabin_class, alert_type, message, triggered_at)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """, (
                airline,
                route["origin"],
                route["destination"],
                route["class"],
                alert_type,
                message,
                datetime.utcnow().isoformat()
            ))

            self.db_conn.commit()
            METRICS["alerts_triggered"].labels(
                airline=airline,
                route=f"{route['origin']}-{route['destination']}",
                class_=route["class"]
            ).inc()

            self.logger.warning(f"ALERT: {alert_type} - {message}")

            # Reset state after alert to avoid spam
            self.alert_state[alert_key] = 0

    def _check_all_airlines(self) -> None:
        """Check award space for all airlines and routes"""
        start_time = time.time()
        self.logger.info("Starting award space monitoring cycle")

        with ThreadPoolExecutor(max_workers=min(10, len(self.config["airlines"]) * len(self.config["routes"]))) as executor:
            futures = []

            for airline_code, airline_info in self.config["airlines"].items():
                for route in self.config["routes"]:
                    futures.append(executor.submit(
                        self._check_single_airline_route,
                        airline_code,
                        airline_info,
                        route
                    ))

            for future in as_completed(futures):
                try:
                    future.result()
                except Exception as e:
                    self.logger.error(f"Error in monitoring cycle: {str(e)}")

        duration = time.time() - start_time
        METRICS["check_duration_seconds"].observe(duration)
        METRICS["checks_total"].inc()
        self.logger.info(f"Monitoring cycle completed in {duration:.2f} seconds")

    def _check_single_airline_route(self, airline_code: str, airline_info: Dict, route: Dict) -> None:
        """Check award space for a single airline and route"""
        try:
            # Get current award space
            award_space = self._get_award_space_from_api(airline_code, route)
            if not award_space:
                return

            # Store in database
            self._store_award_space(award_space)

            # Update Prometheus metrics
            METRICS["current_availability"].labels(
                airline=airline_code,
                route=f"{route['origin']}-{route['destination']}",
                class_=route["class"]
            ).set(1 if award_space.available else 0)

            # Check for changes
            change_result = self._check_for_changes(airline_code, route)
            if change_result:
                has_changed, prev_seats = change_result

                if has_changed:
                    change_type = "AVAILABILITY_OPENED" if award_space.available else "AVAILABILITY_CLOSED"
                    message = (
                        f"{change_type}: {airline_info['name']} {route['origin']}-{route['destination']} "
                        f"{route['class']} class - {award_space.seats} seats available"
                    )

                    self._trigger_alert(airline_code, route, message)

        except Exception as e:
            self.logger.error(f"Error checking {airline_code} {route}: {str(e)}")

    def _cleanup_old_data(self) -> None:
        """Clean up old data from database"""
        try:
            cursor = self.db_conn.cursor()

            # Delete records older than 30 days
            cutoff_date = (datetime.utcnow() - timedelta(days=30)).isoformat()
            cursor.execute("""
            DELETE FROM award_space
            WHERE last_updated < ?
            """, (cutoff_date,))

            deleted_count = cursor.rowcount
            self.db_conn.commit()

            if deleted_count > 0:
                self.logger.info(f"Cleaned up {deleted_count} old records")

        except Exception as e:
            self.logger.error(f"Error cleaning up old data: {str(e)}")

    def run(self) -> None:
        """Main monitoring loop"""
        self.logger.info("Starting Award Space Monitoring System")

        try:
            while True:
                try:
                    self._check_all_airlines()
                    self._cleanup_old_data()
                except Exception as e:
                    self.logger.error(f"Error in monitoring loop: {str(e)}")

                # Sleep until next check
                time.sleep(self.config["check_interval"])

        except KeyboardInterrupt:
            self.logger.info("Shutting down monitoring system...")
        finally:
            if self.db_conn:
                self.db_conn.close()

def main():
    """Entry point for the monitoring system"""
    monitor = AwardMonitoringSystem(CONFIG)
    monitor.run()

if __name__ == "__main__":
    main()
