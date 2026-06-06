from platform.src.intelligence.metrics import AwardTravelMetrics
import numpy as np
from typing import List

class EvaluationPipeline:
    def __init__(self, predicted_award_travel: List[float], actual_award_travel: List[float]):
        self.predicted_award_travel = predicted_award_travel
        self.actual_award_travel = actual_award_travel

    def evaluate(self) -> dict:
        metrics = AwardTravelMetrics(self.predicted_award_travel, self.actual_award_travel)
        return {
            "mean_absolute_error": metrics.mean_absolute_error(),
            "mean_squared_error": metrics.mean_squared_error(),
            "root_mean_squared_error": metrics.root_mean_squared_error(),
            "r2_score": metrics.r2_score()
        }
