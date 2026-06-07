import numpy as np
from platform.src.intelligence.cancellation_policy import CancellationPolicy
from typing import Dict

class CancellationPipeline:
    def __init__(self, policy_config: Dict):
        self.policy_config = policy_config
        self.cancellation_policy = CancellationPolicy(policy_config)

    def process_cancellation(self, booking_data: Dict) -> float:
        """
        Process a cancellation request and calculate the cancellation fee.
        
        Args:
        booking_data (Dict): The booking data, including the booking date and cancellation date.
        
        Returns:
        float: The cancellation fee.
        """
        # Extract the booking and cancellation dates from the booking data
        booking_date = booking_data['booking_date']
        cancellation_date = booking_data['cancellation_date']
        
        # Calculate the cancellation fee using the cancellation policy
        cancellation_fee = self.cancellation_policy.calculate_cancellation_fee(booking_date, cancellation_date)
        
        return cancellation_fee

    def get_cancellation_policy(self) -> Dict:
        """
        Get the cancellation policy configuration.
        
        Returns:
        Dict: The cancellation policy configuration.
        """
        return self.cancellation_policy.get_cancellation_policy()
