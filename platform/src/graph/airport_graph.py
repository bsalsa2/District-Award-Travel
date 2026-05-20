"""
High-performance graph representation for award flight routes.
Uses adjacency lists optimized for cache locality and concurrent access.
"""

import numpy as np
import pandas as pd
from typing import Dict, List, Tuple, Optional
from dataclasses import dataclass
from collections import defaultdict
import threading
import time
from concurrent.futures import ThreadPoolExecutor
import json
from pathlib import Path

@dataclass(frozen=True)
class AirportNode:
    """Immutable airport node with cache-friendly layout."""
    iata: str
    name: str
    city: str
    country: str
    latitude: float
    longitude: float
    timezone: str
    index: int  # Pre-assigned index for array-based access

@dataclass(frozen=True)
class AirlineNode:
    """Immutable airline node."""
    iata: str
    name: str
    alliance: str
    index: int

@dataclass(frozen=True)
class FareClass:
    """Award fare class representation."""
    class_code: str
    name: str
    redemption_value: float  # Points required
    availability_threshold: int  # Minimum seats available
    booking_class: str

@dataclass(frozen=True)
class RouteEdge:
    """Edge representing flight route with award availability."""
    source: AirportNode
    target: AirportNode
    airline: AirlineNode
    fare_class: FareClass
    distance_km: float
    duration_min: int
    base_price: float
    award_price: float
    availability: int
    last_updated: float
    is_direct: bool
    transfer_time_min: Optional[int] = None
    equipment: Optional[str] = None

class AirportGraph:
    """
    High-performance graph for award flight routes.
    Optimized for concurrent reads and batch updates.
    """

    def __init__(self, initial_capacity: int = 10000):
        self._lock = threading.RLock()
        self._airports: Dict[str, AirportNode] = {}
        self._airlines: Dict[str, AirlineNode] = {}
        self._fare_classes: Dict[str, FareClass] = {}
        self._graph: Dict[int, Dict[int, List[RouteEdge]]] = defaultdict(dict)
        self._reverse_graph: Dict[int, Dict[int, List[RouteEdge]]] = defaultdict(dict)
        self._airport_index: Dict[str, int] = {}
        self._airline_index: Dict[str, int] = {}
        self._fare_index: Dict[str, int] = {}
        self._airport_coords: np.ndarray = np.zeros((initial_capacity, 2), dtype=np.float32)
        self._next_airport_index = 0
        self._next_airline_index = 0
        self._next_fare_index = 0
        self._executor = ThreadPoolExecutor(max_workers=8)
        self._cache_hits = 0
        self._cache_misses = 0

    def add_airport(self, airport: AirportNode) -> None:
        """Add airport node with thread-safe indexing."""
        with self._lock:
            if airport.iata not in self._airports:
                if self._next_airport_index >= self._airport_coords.shape[0]:
                    self._resize_arrays()

                self._airports[airport.iata] = airport
                self._airport_index[airport.iata] = self._next_airport_index
                self._airport_coords[self._next_airport_index] = [airport.latitude, airport.longitude]
                airport = AirportNode(
                    iata=airport.iata,
                    name=airport.name,
                    city=airport.city,
                    country=airport.country,
                    latitude=airport.latitude,
                    longitude=airport.longitude,
                    timezone=airport.timezone,
                    index=self._next_airport_index
                )
                self._next_airport_index += 1

    def add_airline(self, airline: AirlineNode) -> None:
        """Add airline node."""
        with self._lock:
            if airline.iata not in self._airlines:
                self._airlines[airline.iata] = AirlineNode(
                    iata=airline.iata,
                    name=airline.name,
                    alliance=airline.alliance,
                    index=self._next_airline_index
                )
                self._airline_index[airline.iata] = self._next_airline_index
                self._next_airline_index += 1

    def add_fare_class(self, fare_class: FareClass) -> None:
        """Add fare class definition."""
        with self._lock:
            if fare_class.class_code not in self._fare_classes:
                self._fare_classes[fare_class.class_code] = fare_class
                self._fare_index[fare_class.class_code] = self._next_fare_index
                self._next_fare_index += 1

    def add_route(self, edge: RouteEdge) -> None:
        """Add route edge with bidirectional indexing."""
        with self._lock:
            src_idx = self._airport_index[edge.source.iata]
            tgt_idx = self._airport_index[edge.target.iata]

            # Add to forward graph
            if tgt_idx not in self._graph[src_idx]:
                self._graph[src_idx][tgt_idx] = []
            self._graph[src_idx][tgt_idx].append(edge)

            # Add to reverse graph
            if src_idx not in self._reverse_graph[tgt_idx]:
                self._reverse_graph[tgt_idx][src_idx] = []
            self._reverse_graph[tgt_idx][src_idx].append(edge)

    def get_airport(self, iata: str) -> Optional[AirportNode]:
        """Get airport node by IATA code."""
        return self._airports.get(iata)

    def get_airline(self, iata: str) -> Optional[AirlineNode]:
        """Get airline node by IATA code."""
        return self._airlines.get(iata)

    def get_fare_class(self, class_code: str) -> Optional[FareClass]:
        """Get fare class by code."""
        return self._fare_classes.get(class_code)

    def get_routes_from(self, iata: str) -> List[RouteEdge]:
        """Get all outgoing routes from airport."""
        idx = self._airport_index.get(iata)
        if idx is None:
            return []
        return [edge for routes in self._graph[idx].values() for edge in routes]

    def get_routes_to(self, iata: str) -> List[RouteEdge]:
        """Get all incoming routes to airport."""
        idx = self._airport_index.get(iata)
        if idx is None:
            return []
        return [edge for routes in self._reverse_graph[idx].values() for edge in routes]

    def find_shortest_path(
        self,
        source_iata: str,
        target_iata: str,
        max_stops: int = 5,
        max_duration: int = 1440,  # 24 hours
        min_availability: int = 1
    ) -> List[RouteEdge]:
        """
        Find shortest path using BFS with constraints.
        Returns list of RouteEdge objects representing the path.
        """
        from collections import deque

        src_idx = self._airport_index.get(source_iata)
        tgt_idx = self._airport_index.get(target_iata)

        if src_idx is None or tgt_idx is None:
            return []

        visited = set()
        queue = deque()
        queue.append((src_idx, []))
        visited.add(src_idx)

        start_time = time.time()

        while queue and (time.time() - start_time) < 1.0:  # 1s timeout
            current_idx, path = queue.popleft()

            if current_idx == tgt_idx:
                return path

            if len(path) >= max_stops:
                continue

            for neighbor_idx, edges in self._graph[current_idx].items():
                if neighbor_idx in visited:
                    continue

                for edge in edges:
                    if edge.availability < min_availability:
                        continue
                    if edge.duration_min > max_duration:
                        continue

                    new_path = path + [edge]
                    visited.add(neighbor_idx)
                    queue.append((neighbor_idx, new_path))

        return []

    def batch_update_availability(self, updates: List[Tuple[str, str, int]]) -> None:
        """
        Batch update route availability atomically.
        updates: List of (source_iata, target_iata, new_availability)
        """
        with self._lock:
            for src_iata, tgt_iata, availability in updates:
                src_idx = self._airport_index.get(src_iata)
                tgt_idx = self._airport_index.get(tgt_iata)

                if src_idx is not None and tgt_idx is not None:
                    if tgt_idx in self._graph[src_idx]:
                        for edge in self._graph[src_idx][tgt_idx]:
                            # Create new edge with updated availability
                            new_edge = RouteEdge(
                                source=edge.source,
                                target=edge.target,
                                airline=edge.airline,
                                fare_class=edge.fare_class,
                                distance_km=edge.distance_km,
                                duration_min=edge.duration_min,
                                base_price=edge.base_price,
                                award_price=edge.award_price,
                                availability=availability,
                                last_updated=time.time(),
                                is_direct=edge.is_direct,
                                transfer_time_min=edge.transfer_time_min,
                                equipment=edge.equipment
                            )
                            self._graph[src_idx][tgt_idx].append(new_edge)

    def get_graph_stats(self) -> Dict:
        """Get performance and size statistics."""
        with self._lock:
            total_edges = sum(len(routes) for routes in self._graph.values())
            total_nodes = len(self._airports)

            return {
                'total_airports': total_nodes,
                'total_airlines': len(self._airlines),
                'total_fare_classes': len(self._fare_classes),
                'total_edges': total_edges,
                'average_degree': total_edges / total_nodes if total_nodes > 0 else 0,
                'cache_hit_rate': self._cache_hits / (self._cache_hits + self._cache_misses) if (self._cache_hits + self._cache_misses) > 0 else 0
            }

    def _resize_arrays(self) -> None:
        """Resize coordinate arrays for growth."""
        new_size = self._airport_coords.shape[0] * 2
        new_coords = np.zeros((new_size, 2), dtype=np.float32)
        new_coords[:self._next_airport_index] = self._airport_coords[:self._next_airport_index]
        self._airport_coords = new_coords

    def to_dict(self) -> Dict:
        """Serialize graph to dict for persistence."""
        with self._lock:
            return {
                'airports': [
                    {
                        'iata': a.iata,
                        'name': a.name,
                        'city': a.city,
                        'country': a.country,
                        'latitude': a.latitude,
                        'longitude': a.longitude,
                        'timezone': a.timezone,
                        'index': a.index
                    } for a in self._airports.values()
                ],
                'airlines': [
                    {
                        'iata': al.iata,
                        'name': al.name,
                        'alliance': al.alliance,
                        'index': al.index
                    } for al in self._airlines.values()
                ],
                'fare_classes': [
                    {
                        'class_code': fc.class_code,
                        'name': fc.name,
                        'redemption_value': fc.redemption_value,
                        'availability_threshold': fc.availability_threshold,
                        'booking_class': fc.booking_class
                    } for fc in self._fare_classes.values()
                ],
                'edges': [
                    {
                        'source': edge.source.iata,
                        'target': edge.target.iata,
                        'airline': edge.airline.iata,
                        'fare_class': edge.fare_class.class_code,
                        'distance_km': edge.distance_km,
                        'duration_min': edge.duration_min,
                        'base_price': edge.base_price,
                        'award_price': edge.award_price,
                        'availability': edge.availability,
                        'last_updated': edge.last_updated,
                        'is_direct': edge.is_direct,
                        'transfer_time_min': edge.transfer_time_min,
                        'equipment': edge.equipment
                    } for edges in self._graph.values() for edge_list in edges.values() for edge in edge_list
                ]
            }

    @classmethod
    def from_dict(cls, data: Dict) -> 'AirportGraph':
        """Load graph from serialized dict."""
        graph = cls()

        # Add airports
        for airport_data in data['airports']:
            airport = AirportNode(
                iata=airport_data['iata'],
                name=airport_data['name'],
                city=airport_data['city'],
                country=airport_data['country'],
                latitude=airport_data['latitude'],
                longitude=airport_data['longitude'],
                timezone=airport_data['timezone'],
                index=airport_data['index']
            )
            graph.add_airport(airport)

        # Add airlines
        for airline_data in data['airlines']:
            airline = AirlineNode(
                iata=airline_data['iata'],
                name=airline_data['name'],
                alliance=airline_data['alliance'],
                index=airline_data['index']
            )
            graph.add_airline(airline)

        # Add fare classes
        for fare_data in data['fare_classes']:
            fare_class = FareClass(
                class_code=fare_data['class_code'],
                name=fare_data['name'],
                redemption_value=fare_data['redemption_value'],
                availability_threshold=fare_data['availability_threshold'],
                booking_class=fare_data['booking_class']
            )
            graph.add_fare_class(fare_class)

        # Add edges
        for edge_data in data['edges']:
            source = graph.get_airport(edge_data['source'])
            target = graph.get_airport(edge_data['target'])
            airline = graph.get_airline(edge_data['airline'])
            fare_class = graph.get_fare_class(edge_data['fare_class'])

            if source and target and airline and fare_class:
                edge = RouteEdge(
                    source=source,
                    target=target,
                    airline=airline,
                    fare_class=fare_class,
                    distance_km=edge_data['distance_km'],
                    duration_min=edge_data['duration_min'],
                    base_price=edge_data['base_price'],
                    award_price=edge_data['award_price'],
                    availability=edge_data['availability'],
                    last_updated=edge_data['last_updated'],
                    is_direct=edge_data['is_direct'],
                    transfer_time_min=edge_data['transfer_time_min'],
                    equipment=edge_data['equipment']
                )
                graph.add_route(edge)

        return graph

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self._executor.shutdown(wait=True)
