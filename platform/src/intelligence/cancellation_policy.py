import numpy as np
from typing import Dict

class CancellationPolicy:
    def __init__(self, policy_config: Dict):
        self.policy_config = policy_config

    def calculate_cancellation_fee(self, booking_date: str, cancellation_date: str) -> float:
        """
        Calculate the cancellation fee based on the policy configuration.
        
        Args:
        booking_date (str): The date the booking was made.
        cancellation_date (str): The date the booking was cancelled.
        
        Returns:
        float: The cancellation fee.
        """
        # Calculate the time difference between the booking and cancellation dates
        time_diff = np.datetime64(cancellation_date) - np.datetime64(booking_date)
        
        # Check if the cancellation is within the free cancellation period
        if time_diff < np.timedelta64(self.policy_config['free_cancellation_period'], 'D'):
            return 0.0
        
        # Calculate the cancellation fee based on the policy configuration
        fee = self.policy_config['cancellation_fee_percentage'] * self.policy_config['booking_price']
        
        return fee

    def get_cancellation_policy(self) -> Dict:
        """
        Get the cancellation policy configuration.
        
        Returns:
        Dict: The cancellation policy configuration.
        """
        return self.policy_config
