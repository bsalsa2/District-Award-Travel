from platform.src.intelligence.award_redemption_simulator import AwardRedemptionSimulator
from typing import List, Dict

class AwardRedemptionPipeline:
    def __init__(self, client_id: int, travel_dates: List[str], destination: str):
        self.client_id = client_id
        self.travel_dates = travel_dates
        self.destination = destination
        self.simulator = AwardRedemptionSimulator(client_id, travel_dates, destination)

    def run_pipeline(self) -> Dict:
        # Run the award redemption pipeline
        simulation_results = self.simulator.simulate_redemption()
        return simulation_results

    def get_redemption_options(self) -> List[Dict]:
        # Return a list of redemption options for the client
        return self.simulator.get_redemption_options()
