from py2neo import Graph, Node, Relationship

class GraphService:
    def __init__(self, graph):
        self.graph = graph

    def get_availability(self, query):
        results = self.graph.run("MATCH (n:Availability {query: $query}) RETURN n", query=query)
        return [record["n"] for record in results]

    def get_pricing(self, query):
        results = self.graph.run("MATCH (n:Pricing {query: $query}) RETURN n", query=query)
        return [record["n"] for record in results]
