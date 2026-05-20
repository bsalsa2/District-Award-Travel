import json
from typing import Optional, List
import redis
from .config import settings
from .models import Alert, EscalationState

class AlertStorage:
    def __init__(self):
        self.redis = redis.Redis(
            host=settings.REDIS_HOST,
            port=settings.REDIS_PORT,
            password=settings.REDIS_PASSWORD,
            decode_responses=True
        )

    def store_alert(self, alert: Alert) -> bool:
        key = f"alert:{alert.alert_id}"
        serialized = alert.json()
        return self.redis.set(key, serialized)

    def get_alert(self, alert_id: str) -> Optional[Alert]:
        key = f"alert:{alert_id}"
        data = self.redis.get(key)
        if data:
            return Alert.parse_raw(data)
        return None

    def update_alert(self, alert: Alert) -> bool:
        return self.store_alert(alert)

    def acknowledge_alert(self, alert_id: str, user: str) -> bool:
        alert = self.get_alert(alert_id)
        if alert:
            alert.acknowledged = True
            alert.acknowledged_by = user
            alert.acknowledged_at = datetime.utcnow()
            return self.update_alert(alert)
        return False

    def store_escalation_state(self, state: EscalationState) -> bool:
        key = f"escalation:{state.alert_id}"
        serialized = state.json()
        return self.redis.set(key, serialized)

    def get_escalation_state(self, alert_id: str) -> Optional[EscalationState]:
        key = f"escalation:{alert_id}"
        data = self.redis.get(key)
        if data:
            return EscalationState.parse_raw(data)
        return None

    def list_active_alerts(self) -> List[Alert]:
        keys = self.redis.keys("alert:*")
        alerts = []
        for key in keys:
            data = self.redis.get(key)
            if data:
                alert = Alert.parse_raw(data)
                if not alert.acknowledged:
                    alerts.append(alert)
        return alerts

    def cleanup_resolved_alerts(self, older_than_minutes: int = 1440) -> int:
        """Clean up alerts older than specified minutes"""
        cutoff = datetime.utcnow() - timedelta(minutes=older_than_minutes)
        keys = self.redis.keys("alert:*")
        count = 0
        for key in keys:
            data = self.redis.get(key)
            if data:
                alert = Alert.parse_raw(data)
                if alert.timestamp < cutoff:
                    self.redis.delete(key)
                    count += 1
        return count
