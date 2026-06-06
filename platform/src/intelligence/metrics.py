import numpy as np
from typing import List

class AwardTravelMetrics:
    def __init__(self, predicted_award_travel: List[float], actual_award_travel: List[float]):
        self.predicted_award_travel = predicted_award_travel
        self.actual_award_travel = actual_award_travel

    def mean_absolute_error(self) -> float:
        return np.mean([abs(predicted - actual) for predicted, actual in zip(self.predicted_award_travel, self.actual_award_travel)])

    def mean_squared_error(self) -> float:
        return np.mean([(predicted - actual) ** 2 for predicted, actual in zip(self.predicted_award_travel, self.actual_award_travel)])

    def root_mean_squared_error(self) -> float:
        return np.sqrt(self.mean_squared_error())

    def r2_score(self) -> float:
        mean_actual = np.mean(self.actual_award_travel)
        ss_res = np.sum([(predicted - actual) ** 2 for predicted, actual in zip(self.predicted_award_travel, self.actual_award_travel)])
        ss_tot = np.sum([(actual - mean_actual) ** 2 for actual in self.actual_award_travel])
        return 1 - (ss_res / ss_tot)
