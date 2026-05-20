from datetime import datetime, timedelta
from typing import List, Dict
from .models import Alert, EscalationState, EscalationEvent
from .storage import AlertStorage
from .config import settings
import logging

logger = logging.getLogger(__name__)

class EscalationEngine:
    def __init__(self):
        self.storage = AlertStorage()
        self.policies = settings.DEFAULT_POLICIES

    def match_policy(self, alert: Alert) -> Optional[AlertPolicy]:
        for policy in self.policies:
            match = True
            for field, value in policy.match_fields.items():
                if field not in alert.metadata or alert.metadata[field] != value:
                    match = False
                    break
            if match:
                return policy
        return None

    def create_escalation_state(self, alert: Alert) -> EscalationState:
        policy = self.match_policy(alert)
        if not policy:
            logger.warning(f"No policy matched for alert {alert.alert_id}")
            return None

        state = EscalationState(
            alert_id=alert.alert_id,
            current_level=0,
            next_escalation_time=datetime.utcnow() + timedelta(minutes=policy.escalation_levels[0].wait_minutes)
        )
        return state

    def should_escalate(self, state: EscalationState) -> bool:
        if state.acknowledged:
            return False

        if datetime.utcnow() >= state.next_escalation_time:
            return True

        return False

    def perform_escalation(self, state: EscalationState) -> List[EscalationEvent]:
        if not self.should_escalate(state):
            return []

        policy = self._get_policy_for_alert(state.alert_id)
        if not policy:
            return []

        current_level = state.current_level + 1
        if current_level >= len(policy.escalation_levels):
            logger.info(f"Max escalation level reached for alert {state.alert_id}")
            return []

        level_config = policy.escalation_levels[current_level]

        events = []
        for channel in level_config.channels:
            if not channel.enabled:
                continue

            event = EscalationEvent(
                alert_id=state.alert_id,
                policy_id=policy.policy_id,
                level=current_level,
                channel=channel.type,
                destination=channel.destination,
                timestamp=datetime.utcnow()
            )

            success = self._send_notification(event, channel)
            event.sent = success
            event.response_status = "success" if success else "failed"
            events.append(event)

            state.escalation_history.append(event)

        state.current_level = current_level
        state.next_escalation_time = datetime.utcnow() + timedelta(minutes=level_config.wait_minutes)
        self.storage.store_escalation_state(state)

        return events

    def _get_policy_for_alert(self, alert_id: str) -> Optional[AlertPolicy]:
        alert = self.storage.get_alert(alert_id)
        if alert:
            return self.match_policy(alert)
        return None

    def _send_notification(self, event: EscalationEvent, channel: NotificationChannel) -> bool:
        try:
            if channel.type == "slack":
                return self._send_slack_notification(event, channel)
            elif channel.type == "email":
                return self._send_email_notification(event, channel)
            elif channel.type == "pagerduty":
                return self._send_pagerduty_notification(event, channel)
            else:
                logger.warning(f"Unknown notification channel type: {channel.type}")
                return False
        except Exception as e:
            logger.error(f"Failed to send notification: {e}")
            return False

    def _send_slack_notification(self, event: EscalationEvent, channel: NotificationChannel) -> bool:
        import requests
        message = f"""
        🚨 *Escalation Alert* 🚨
        *Policy:* {event.policy_id}
        *Level:* {event.level}
        *Alert ID:* {event.alert_id}
        *Message:* {self._get_alert_message(event.alert_id)}
        *Time:* {event.timestamp.isoformat()}
        """

        response = requests.post(
            channel.destination,
            json={"text": message},
            timeout=10
        )
        return response.status_code == 200

    def _send_email_notification(self, event: EscalationEvent, channel: NotificationChannel) -> bool:
        import smtplib
        from email.mime.text import MIMEText

        alert = self.storage.get_alert(event.alert_id)
        if not alert:
            return False

        message = f"""
        Subject: [Escalation] {event.policy_id} - Level {event.level}

        Alert Escalation Notification
        =============================

        Policy: {event.policy_id}
        Level: {event.level}
        Alert ID: {event.alert_id}
        Severity: {alert.severity}
        Message: {alert.message}
        Source: {alert.source}
        Timestamp: {alert.timestamp.isoformat()}

        Please acknowledge this alert in the escalation system.
        """

        try:
            msg = MIMEText(message)
            msg['Subject'] = f"[Escalation] {event.policy_id} - Level {event.level}"
            msg['From'] = settings.EMAIL_FROM
            msg['To'] = channel.destination

            with smtplib.SMTP(
                settings.EMAIL_SMTP_HOST,
                settings.EMAIL_SMTP_PORT
            ) as server:
                server.starttls()
                # In production, use proper authentication
                server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Email notification failed: {e}")
            return False

    def _send_pagerduty_notification(self, event: EscalationEvent, channel: NotificationChannel) -> bool:
        import requests

        alert = self.storage.get_alert(event.alert_id)
        if not alert:
            return False

        payload = {
            "routing_key": channel.destination,
            "event_action": "trigger",
            "payload": {
                "summary": f"Escalation: {event.policy_id} - Level {event.level}",
                "source": alert.source,
                "severity": alert.severity,
                "custom_details": {
                    "alert_id": event.alert_id,
                    "message": alert.message,
                    "timestamp": alert.timestamp.isoformat()
                }
            }
        }

        response = requests.post(
            "https://events.pagerduty.com/v2/enqueue",
            json=payload,
            headers={"Content-Type": "application/json"},
            timeout=10
        )
        return response.status_code == 202

    def _get_alert_message(self, alert_id: str) -> str:
        alert = self.storage.get_alert(alert_id)
        if alert:
            return alert.message
        return "Alert message not available"
