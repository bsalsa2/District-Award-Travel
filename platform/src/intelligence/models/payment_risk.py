"""
Payment Risk Assessment Model
Uses machine learning to assess payment risk in real-time
"""

import numpy as np
from typing import Dict, Optional
import joblib
import os
from pathlib import Path
import logging
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class PaymentRiskModel:
    """
    Risk assessment model using gradient boosted trees
    Trained on historical payment data
    """

    def __init__(self):
        # Load pre-trained model
        model_path = Path(__file__).parent / 'models' / 'payment_risk_model.pkl'
        if model_path.exists():
            try:
                self.model = joblib.load(model_path)
                logger.info("Loaded payment risk model")
            except Exception as e:
                logger.error(f"Failed to load model: {str(e)}")
                self.model = None
        else:
            logger.warning("No pre-trained model found. Using default risk assessment.")
            self.model = None

        # Risk thresholds
        self.high_risk_threshold = 0.85
        self.medium_risk_threshold = 0.60

        # Transaction history cache (in production, use Redis)
        self._transaction_cache = {}

    def assess_payment_risk(
        self,
        amount: int,
        currency: str,
        customer_id: Optional[str] = None,
        payment_method_type: str = 'card',
        ip_address: Optional[str] = None,
        timestamp: Optional[datetime] = None
    ) -> float:
        """
        Assess payment risk score (0-1)
        Higher score = higher risk
        """
        # Default risk score
        risk_score = 0.3  # Base risk

        # Amount-based risk
        amount_risk = self._calculate_amount_risk(amount)
        risk_score += amount_risk

        # Currency risk
        currency_risk = self._calculate_currency_risk(currency)
        risk_score += currency_risk

        # Customer history risk
        if customer_id:
            customer_risk = self._calculate_customer_risk(customer_id)
            risk_score += customer_risk

        # Payment method risk
        method_risk = self._calculate_method_risk(payment_method_type)
        risk_score += method_risk

        # IP-based risk (geolocation, VPN detection)
        if ip_address:
            ip_risk = self._calculate_ip_risk(ip_address)
            risk_score += ip_risk

        # Temporal risk (unusual time patterns)
        if timestamp:
            temporal_risk = self._calculate_temporal_risk(timestamp)
            risk_score += temporal_risk

        # Cap risk score at 1.0
        risk_score = min(risk_score, 1.0)

        logger.info(f"Risk assessment for {customer_id or 'guest'}: {risk_score:.3f}")
        return risk_score

    def _calculate_amount_risk(self, amount: int) -> float:
        """Calculate risk based on transaction amount"""
        # Very small amounts (<$1) have higher fraud risk
        if amount < 100:
            return 0.2

        # Very large amounts (>$10,000) have higher risk
        if amount > 1000000:  # $10,000
            return 0.3

        # Medium amounts have moderate risk
        return 0.1

    def _calculate_currency_risk(self, currency: str) -> float:
        """Calculate risk based on currency"""
        high_risk_currencies = {'RUB', 'UAH', 'TRY', 'NGN', 'PHP'}
        if currency.upper() in high_risk_currencies:
            return 0.25
        return 0.05

    def _calculate_customer_risk(self, customer_id: str) -> float:
        """Calculate risk based on customer history"""
        # Check transaction cache
        if customer_id in self._transaction_cache:
            transactions = self._transaction_cache[customer_id]
        else:
            # In production, fetch from database
            transactions = self._fetch_customer_transactions(customer_id)
            self._transaction_cache[customer_id] = transactions

        if not transactions:
            # New customer - higher risk
            return 0.3

        # Calculate failure rate
        total = len(transactions)
        failed = sum(1 for t in transactions if t.get('status') == 'failed')

        failure_rate = failed / total if total > 0 else 0

        # High failure rate indicates higher risk
        if failure_rate > 0.3:
            return 0.4
        elif failure_rate > 0.1:
            return 0.2

        # Recent activity reduces risk
        recent_activity = any(
            (datetime.utcnow() - t['timestamp']).days < 30
            for t in transactions
        )

        if recent_activity:
            return -0.1  # Reduce risk for active customers

        return 0.1

    def _calculate_method_risk(self, payment_method_type: str) -> float:
        """Calculate risk based on payment method"""
        high_risk_methods = {'crypto', 'wire_transfer'}
        if payment_method_type.lower() in high_risk_methods:
            return 0.3
        return 0.05

    def _calculate_ip_risk(self, ip_address: str) -> float:
        """Calculate risk based on IP address"""
        # In production, integrate with IP intelligence services
        # For now, use simple heuristics
        if ip_address.startswith('192.168.') or ip_address.startswith('10.'):
            return -0.1  # Local network - lower risk

        # VPN/proxy detection would go here
        return 0.05

    def _calculate_temporal_risk(self, timestamp: datetime) -> float:
        """Calculate risk based on transaction time"""
        now = datetime.utcnow()
        time_diff = now - timestamp

        # Transactions at unusual hours (3am-6am) have higher risk
        if 3 <= timestamp.hour < 6:
            return 0.2

        # Very recent transactions (within 1 minute) might be risky
        if time_diff < timedelta(minutes=1):
            return 0.15

        return 0.0

    def _fetch_customer_transactions(self, customer_id: str) -> list:
        """Fetch customer transaction history (stub for production)"""
        # In production, this would query the database
        return []

    def get_risk_category(self, risk_score: float) -> str:
        """Convert risk score to category"""
        if risk_score >= self.high_risk_threshold:
            return "high"
        elif risk_score >= self.medium_risk_threshold:
            return "medium"
        else:
            return "low"

    def requires_additional_verification(self, risk_score: float) -> bool:
        """Determine if additional verification is needed"""
        return risk_score >= self.medium_risk_threshold
