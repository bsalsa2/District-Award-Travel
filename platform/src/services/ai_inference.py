import torch
import numpy as np
import json
from typing import Dict, Any, List
from pathlib import Path
import logging
from datetime import datetime, timedelta
import redis
from config.settings import settings
import time

logger = logging.getLogger(__name__)

class AwardPredictor:
    def __init__(self):
        self.device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
        self.model = self._load_model()
        self.redis = redis.Redis.from_url(settings.REDIS_URL)

    def _load_model(self):
        """Load the trained transformer model with TensorRT optimization"""
        try:
            # Load NVIDIA NeMo model
            model = torch.jit.load(settings.TENSORRT_ENGINE)
            model.to(self.device)
            model.eval()
            logger.info("AI model loaded successfully")
            return model
        except Exception as e:
            logger.error(f"Failed to load AI model: {e}")
            raise

    def _preprocess_input(self, route_key: str, departure_date: datetime, passengers: int) -> Dict[str, Any]:
        """Convert input to model-ready format"""
        # Extract features from route key
        origin, destination, cabin_class = route_key.split('_')

        # Calculate temporal features
        departure_day = departure_date.day
        departure_month = departure_date.month
        departure_day_of_week = departure_date.weekday()
        days_until_departure = (departure_date - datetime.now()).days

        # Load historical data from cache
        historical_data = self._get_historical_data(route_key)

        return {
            "origin": origin,
            "destination": destination,
            "cabin_class": cabin_class,
            "passengers": passengers,
            "departure_day": departure_day,
            "departure_month": departure_month,
            "departure_day_of_week": departure_day_of_week,
            "days_until_departure": days_until_departure,
            **historical_data
        }

    def _get_historical_data(self, route_key: str) -> Dict[str, Any]:
        """Retrieve historical patterns from Redis cache"""
        cache_key = f"historical:{route_key}"
        cached = self.redis.get(cache_key)
        if cached:
            return json.loads(cached)

        # Fallback to default values if not in cache
        return {
            "historical_availability": 0.75,
            "historical_price": 50000,
            "seasonality_factor": 1.0,
            "trend_factor": 1.0
        }

    def predict(self, route_key: str, departure_date: datetime, passengers: int = 1) -> Dict[str, Any]:
        """Make prediction using the AI model"""
        start_time = time.time()

        # Check cache first
        cache_key = f"pred:{route_key}:{departure_date.strftime('%Y%m%d')}"
        cached = self.redis.get(cache_key)
        if cached:
            logger.info(f"Cache hit for {cache_key}")
            return json.loads(cached)

        # Preprocess input
        input_data = self._preprocess_input(route_key, departure_date, passengers)
        input_tensor = self._convert_to_tensor(input_data)

        # Run inference
        with torch.no_grad():
            output = self.model(input_tensor)

        # Process output
        prediction = self._process_output(output, input_data)

        # Cache result
        self.redis.setex(
            cache_key,
            settings.PREDICTION_CACHE_TTL,
            json.dumps(prediction)
        )

        latency = time.time() - start_time
        logger.info(f"Prediction completed in {latency:.4f}s for {route_key}")

        return prediction

    def _convert_to_tensor(self, input_data: Dict[str, Any]) -> torch.Tensor:
        """Convert input data to tensor format expected by model"""
        # Convert categorical features to embeddings
        # This would be model-specific implementation
        features = [
            input_data["origin"],
            input_data["destination"],
            input_data["cabin_class"],
            input_data["departure_day"],
            input_data["departure_month"],
            input_data["departure_day_of_week"],
            input_data["days_until_departure"],
            input_data["passengers"],
            input_data["historical_availability"],
            input_data["historical_price"],
            input_data["seasonality_factor"],
            input_data["trend_factor"]
        ]

        # Convert to tensor (simplified - actual implementation would use proper embeddings)
        tensor = torch.tensor(features, dtype=torch.float32).unsqueeze(0)
        return tensor.to(self.device)

    def _process_output(self, output: torch.Tensor, input_data: Dict[str, Any]) -> Dict[str, Any]:
        """Convert model output to human-readable prediction"""
        # Simplified processing - actual implementation would decode transformer output
        raw_output = output.cpu().numpy()[0]

        # Determine status based on predicted availability
        predicted_availability = raw_output[0]
        confidence = float(raw_output[1])

        if predicted_availability > 0.8:
            status = "high_availability"
        elif predicted_availability > 0.6:
            status = "medium_availability"
        elif predicted_availability > 0.4:
            status = "low_availability"
        else:
            status = "critical_availability"

        # Generate factors influencing prediction
        factors = self._generate_factors(input_data, predicted_availability)

        return {
            "route_key": f"{input_data['origin']}_{input_data['destination']}_{input_data['cabin_class']}",
            "departure_date": input_data["departure_date"].isoformat(),
            "status": status,
            "confidence": confidence,
            "predicted_availability": float(predicted_availability),
            "historical_average": float(input_data["historical_availability"]),
            "price_forecast": {
                "low": float(raw_output[2]),
                "median": float(raw_output[3]),
                "high": float(raw_output[4])
            },
            "factors": factors,
            "recommended_actions": self._generate_recommendations(status, confidence),
            "model_version": "v2.1.0",
            "generated_at": datetime.utcnow().isoformat()
        }

    def _generate_factors(self, input_data: Dict[str, Any], predicted_availability: float) -> List[str]:
        """Generate human-readable factors affecting prediction"""
        factors = []

        # Seasonality check
        if input_data["departure_month"] in [12, 1, 2]:
            factors.append("winter_peak")
        elif input_data["departure_month"] in [6, 7, 8]:
            factors.append("summer_peak")

        # Days until departure
        if input_data["days_until_departure"] < 7:
            factors.append("last_minute")
        elif input_data["days_until_departure"] > 30:
            factors.append("advance_booking")

        # Historical patterns
        if predicted_availability > input_data["historical_availability"] * 1.2:
            factors.append("above_average_availability")
        elif predicted_availability < input_data["historical_availability"] * 0.8:
            factors.append("below_average_availability")

        return factors

    def _generate_recommendations(self, status: str, confidence: float) -> List[str]:
        """Generate actionable recommendations"""
        recommendations = []

        if status == "high_availability":
            recommendations.extend([
                "Book now for best selection",
                "Consider flexible dates for better pricing",
                "Monitor for price drops"
            ])
        elif status == "medium_availability":
            recommendations.extend([
                "Book within 48 hours",
                "Check multiple dates",
                "Consider alternative routes"
            ])
        elif status == "low_availability":
            recommendations.extend([
                "Book immediately",
                "Consider premium cabin for better availability",
                "Set price alerts"
            ])
        else:  # critical
            recommendations.extend([
                "Book immediately or consider alternative destinations",
                "Contact airline directly for group bookings",
                "Set up predictive hold"
            ])

        if confidence < 0.7:
            recommendations.append("Verify with airline directly")

        return recommendations

    async def batch_predict(self, requests: List[Dict]) -> List[Dict]:
        """Process multiple predictions efficiently"""
        results = []
        for req in requests:
            prediction = self.predict(
                req["route_key"],
                datetime.fromisoformat(req["departure_date"]),
                req.get("passengers", 1)
            )
            results.append(prediction)
        return results
