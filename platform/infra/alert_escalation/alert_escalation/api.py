from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from .models import Alert, EscalationState
from .engine import EscalationEngine
from .storage import AlertStorage
from .config import settings
import logging
import sentry_sdk
from sentry_sdk.integrations.fastapi import FastApiIntegration
from prometheus_client import start_http_server, Counter, Gauge

# Initialize monitoring
start_http_server(settings.METRICS_PORT)

# Metrics
ALERTS_RECEIVED = Counter(
    'alerts_received_total',
    'Total number of alerts received'
)
ALERTS_ACKNOWLEDGED = Counter(
    'alerts_acknowledged_total',
    'Total number of alerts acknowledged'
)
ESCALATIONS_PERFORMED = Counter(
    'escalations_performed_total',
    'Total number of escalations performed',
    ['level']
)
ACTIVE_ALERTS = Gauge(
    'active_alerts',
    'Number of active (unacknowledged) alerts'
)

# Initialize Sentry if configured
if settings.SENTRY_DSN:
    sentry_sdk.init(
        dsn=settings.SENTRY_DSN,
        integrations=[FastApiIntegration()],
        traces_sample_rate=1.0
    )

app = FastAPI(title="District Award Travel Alert Escalation API")

# CORS configuration
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Initialize components
storage = AlertStorage()
engine = EscalationEngine()
logger = logging.getLogger(__name__)

@app.post("/alerts")
async def receive_alert(alert: Alert, background_tasks: BackgroundTasks):
    """Receive a new alert and trigger escalation"""
    ALERTS_RECEIVED.inc()

    # Store the alert
    storage.store_alert(alert)

    # Create escalation state
    state = engine.create_escalation_state(alert)
    if state:
        storage.store_escalation_state(state)

        # Trigger initial escalation check
        background_tasks.add_task(process_escalations)

    ACTIVE_ALERTS.inc()
    return {"status": "received", "alert_id": alert.alert_id}

@app.post("/alerts/{alert_id}/acknowledge")
async def acknowledge_alert(alert_id: str, user: str):
    """Acknowledge an alert"""
    success = storage.acknowledge_alert(alert_id, user)
    if not success:
        raise HTTPException(status_code=404, detail="Alert not found")

    ALERTS_ACKNOWLEDGED.inc()
    ACTIVE_ALERTS.dec()
    return {"status": "acknowledged", "alert_id": alert_id}

@app.get("/alerts/{alert_id}")
async def get_alert(alert_id: str):
    """Get alert details"""
    alert = storage.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=404, detail="Alert not found")
    return alert

@app.get("/alerts")
async def list_alerts():
    """List all active alerts"""
    alerts = storage.list_active_alerts()
    return {"alerts": alerts, "count": len(alerts)}

@app.get("/escalation/{alert_id}")
async def get_escalation_state(alert_id: str):
    """Get escalation state for an alert"""
    state = storage.get_escalation_state(alert_id)
    if not state:
        raise HTTPException(status_code=404, detail="Escalation state not found")
    return state

@app.post("/escalation/{alert_id}/process")
async def process_escalations(alert_id: str = None):
    """Process escalations for all alerts or a specific alert"""
    if alert_id:
        state = storage.get_escalation_state(alert_id)
        if state:
            events = engine.perform_escalation(state)
            for event in events:
                ESCALATIONS_PERFORMED.labels(level=event.level).inc()
            return {"status": "processed", "events": len(events)}
        raise HTTPException(status_code=404, detail="Alert not found")
    else:
        alerts = storage.list_active_alerts()
        total_events = 0
        for alert in alerts:
            state = storage.get_escalation_state(alert.alert_id)
            if state:
                events = engine.perform_escalation(state)
                total_events += len(events)
                for event in events:
                    ESCALATIONS_PERFORMED.labels(level=event.level).inc()
        return {"status": "processed", "total_events": total_events}

@app.get("/health")
async def health_check():
    """Health check endpoint"""
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

@app.get("/metrics")
async def metrics():
    """Prometheus metrics endpoint"""
    from prometheus_client import generate_latest, CONTENT_TYPE_LATEST
    return generate_latest(), 200, {'Content-Type': CONTENT_TYPE_LATEST}
