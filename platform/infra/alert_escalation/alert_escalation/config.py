import os
from typing import Dict, List, Optional
from pydantic import BaseSettings, BaseModel

class NotificationChannel(BaseModel):
    type: str
    destination: str
    enabled: bool = True
    rate_limit: int = 3600  # per hour

class EscalationLevel(BaseModel):
    level: int
    wait_minutes: int
    channels: List[NotificationChannel]
    teams: List[str]

class AlertPolicy(BaseModel):
    policy_id: str
    name: str
    severity: str
    match_fields: Dict[str, str]
    escalation_levels: List[EscalationLevel]
    auto_resolve_after_minutes: Optional[int] = None

class Settings(BaseSettings):
    # Redis configuration
    REDIS_HOST: str = "redis"
    REDIS_PORT: int = 6379
    REDIS_PASSWORD: Optional[str] = None

    # Notification services
    SLACK_WEBHOOK_URL: Optional[str] = None
    PAGERDUTY_API_KEY: Optional[str] = None
    EMAIL_SMTP_HOST: Optional[str] = None
    EMAIL_SMTP_PORT: int = 587
    EMAIL_FROM: Optional[str] = None
    EMAIL_TO: Optional[str] = None

    # API configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000

    # Sentry for error tracking
    SENTRY_DSN: Optional[str] = None

    # Prometheus metrics
    METRICS_PORT: int = 9090

    # Teams configuration
    TEAMS: Dict[str, List[str]] = {
        "operations": ["ops-lead@district.travel", "ops-team@district.travel"],
        "engineering": ["eng-lead@district.travel", "eng-team@district.travel"],
        "executive": ["ceo@district.travel", "coo@district.travel"],
        "travel_support": ["travel-support@district.travel"]
    }

    # Default escalation policies
    DEFAULT_POLICIES: List[AlertPolicy] = [
        AlertPolicy(
            policy_id="high-severity-alerts",
            name="High Severity Alerts",
            severity="high",
            match_fields={"severity": "high"},
            escalation_levels=[
                EscalationLevel(
                    level=1,
                    wait_minutes=5,
                    channels=[
                        NotificationChannel(
                            type="slack",
                            destination="#ops-alerts",
                            enabled=True
                        ),
                        NotificationChannel(
                            type="email",
                            destination="ops-lead@district.travel",
                            enabled=True
                        )
                    ],
                    teams=["operations"]
                ),
                EscalationLevel(
                    level=2,
                    wait_minutes=15,
                    channels=[
                        NotificationChannel(
                            type="slack",
                            destination="#executive-alerts",
                            enabled=True
                        ),
                        NotificationChannel(
                            type="pagerduty",
                            destination="pagerduty-service-id",
                            enabled=True
                        )
                    ],
                    teams=["executive", "operations"]
                )
            ],
            auto_resolve_after_minutes=120
        ),
        AlertPolicy(
            policy_id="travel-booking-failures",
            name="Travel Booking Failures",
            severity="critical",
            match_fields={"component": "booking-service", "type": "failure"},
            escalation_levels=[
                EscalationLevel(
                    level=1,
                    wait_minutes=2,
                    channels=[
                        NotificationChannel(
                            type="slack",
                            destination="#travel-support-alerts",
                            enabled=True
                        ),
                        NotificationChannel(
                            type="email",
                            destination="travel-support@district.travel",
                            enabled=True
                        )
                    ],
                    teams=["travel_support"]
                ),
                EscalationLevel(
                    level=2,
                    wait_minutes=10,
                    channels=[
                        NotificationChannel(
                            type="slack",
                            destination="#executive-alerts",
                            enabled=True
                        ),
                        NotificationChannel(
                            type="pagerduty",
                            destination="travel-booking-service",
                            enabled=True
                        )
                    ],
                    teams=["executive", "travel_support"]
                )
            ]
        )
    ]

    class Config:
        env_file = ".env"
        env_file_encoding = 'utf-8'

settings = Settings()
