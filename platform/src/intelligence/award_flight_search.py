import numpy as np
from platform.src.pipeline import AwardFlightPipeline

class AwardFlightSearch:
    def __init__(self):
        self.pipeline = AwardFlightPipeline()

    def search_flights(self, search_request):
        results = self.pipeline.search_flights(search_request)
        return results
