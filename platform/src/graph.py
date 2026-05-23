import asyncio
import networkx as nx
from sqlalchemy import create_engine, Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker

Base = declarative_base()

class Route(Base):
    __tablename__ = "routes"
    id = Column(Integer, primary_key=True)
    origin = Column(String)
    destination = Column(String)
    airline = Column(String)
    award_miles = Column(Integer)

class Graph:
    def __init__(self):
        self.engine = create_engine("sqlite:///routes.db")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)
        self.session = self.Session()
        self.graph = nx.DiGraph()

    async def load_data(self):
        # Load the route data from the database
        routes = self.session.query(Route).all()
        
        # Add the routes to the graph
        for route in routes:
            self.graph.add_edge(route.origin, route.destination, airline=route.airline, award_miles=route.award_miles)

    async def search_routes(self, query):
        # Search for routes using the graph
        routes = []
        for path in nx.all_simple_paths(self.graph, source=query["origin"], target=query["destination"]):
            route = {
                "origin": path[0],
                "destination": path[-1],
                "airline": self.graph.get_edge_data(path[0], path[1])["airline"],
                "award_miles": self.graph.get_edge_data(path[0], path[1])["award_miles"]
            }
            routes.append(route)
        
        return routes

    async def get_route(self, route_id):
        # Get the route details from the graph
        route = self.session.query(Route).filter_by(id=route_id).first()
        
        return {
            "origin": route.origin,
            "destination": route.destination,
            "airline": route.airline,
            "award_miles": route.award_miles
        }
