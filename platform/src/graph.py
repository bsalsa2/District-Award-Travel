import networkx as nx
from typing import Dict, List

class Graph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def add_edge(self, origin: str, destination: str, weight: float):
        self.graph.add_edge(origin, destination, weight=weight)

    def get_shortest_path(self, origin: str, destination: str):
        return nx.shortest_path(self.graph, origin, destination, weight="weight")

    def get_all_paths(self, origin: str, destination: str):
        return list(nx.all_simple_paths(self.graph, origin, destination))
