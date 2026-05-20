from datetime import datetime
from typing import Dict, List, Optional
from pydantic import BaseModel

class Alert(BaseModel):
    alert_id: str
    policy_id: str
    severity: str
    message: str
    source: str
    timestamp: datetime
    acknowledged: bool = False
    acknowledged_by: Optional[str] = None
    acknowledged_at: Optional[datetime] = None
    escalated: bool = False
    escalation_level: int = 0
    metadata: Dict[str, str] = {}

class EscalationEvent(BaseModel):
    alert_id: str
    policy_id: str
    level: int
    channel: str
    destination: str
    timestamp: datetime
    sent: bool = False
    response_status: Optional[str] = None

class EscalationState(BaseModel):
    alert_id: str
    current_level: int
    next_escalation_time: datetime
    escalation_history: List[EscalationEvent] = []
    acknowledged: bool = False
