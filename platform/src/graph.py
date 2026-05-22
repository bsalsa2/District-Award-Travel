import networkx as nx
import numpy as np

class Graph:
    def __init__(self):
        self.graph = nx.DiGraph()

    def update(self, data):
        # Update graph with historical data
        for item in data:
            self.graph.add_node(item["id"])
            for neighbor in item["neighbors"]:
                self.graph.add_edge(item["id"], neighbor)

    def get_nodes(self):
        return list(self.graph.nodes)

    def get_edges(self):
        return list(self.graph.edges)
