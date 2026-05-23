from platform.src.graph import Graph
from typing import Dict, List

class Optimizer:
    def __init__(self, graph: Graph):
        self.graph = graph

    def optimize(self, origin: str, destination: str, travel_date: str, travel_class: str, prices: Dict, availability_status: Dict):
        # Get all possible paths from origin to destination
        all_paths = self.graph.get_all_paths(origin, destination)

        # Initialize optimized route and cost
        optimized_route = None
        optimized_cost = float("inf")

        # Iterate over all possible paths
        for path in all_paths:
            # Calculate total cost for current path
            total_cost = 0
            for i in range(len(path) - 1):
                origin = path[i]
                destination = path[i + 1]
                total_cost += prices.get((origin, destination), float("inf"))

            # Check if current path is more optimal than previous ones
            if total_cost < optimized_cost and availability_status.get((origin, destination), False):
                optimized_route = path
                optimized_cost = total_cost

        return optimized_route
