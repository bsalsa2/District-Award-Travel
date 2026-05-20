"""
Vector embeddings for award flight routes using NVIDIA RAPIDS cuDF/cuGraph.
Fallback to CPU-based implementations when GPU unavailable.
"""

import numpy as np
import pandas as pd
from typing import List, Dict, Tuple, Optional
from dataclasses import asdict
import time
from pathlib import Path
import json
from enum import Enum

try:
    import cudf
    import cuml
    from cugraph import Graph
    HAS_GPU = True
except ImportError:
    import pandas as cudf
    from sklearn.manifold import TSNE
    from sklearn.decomposition import PCA
    HAS_GPU = False

from ..graph.airport_graph import AirportGraph, RouteEdge, AirportNode, AirlineNode

class EmbeddingType(Enum):
    """Types of route embeddings to generate."""
    ROUTE_ONLY = "route_only"
    AIRLINE_AWARE = "airline_aware"
    FARE_CLASS_AWARE = "fare_class_aware"
    FULL_CONTEXT = "full_context"

class RouteVectorizer:
    """
    Generates vector embeddings for award flight routes.
    Optimized for both GPU (RAPIDS) and CPU fallbacks.
    """

    def __init__(self, embedding_dim: int = 128, gpu_memory_limit: float = 0.8):
        self.embedding_dim = embedding_dim
        self.gpu_memory_limit = gpu_memory_limit
        self._feature_scaler = cuml.preprocessing.StandardScaler() if HAS_GPU else None
        self._pca = cuml.decomposition.PCA(n_components=embedding_dim) if HAS_GPU else PCA(n_components=embedding_dim)
        self._model = None
        self._is_trained = False

    def _extract_route_features(self, edge: RouteEdge) -> Dict:
        """Extract numerical features from a route edge."""
        return {
            'distance_km': edge.distance_km,
            'duration_min': edge.duration_min,
            'base_price': edge.base_price,
            'award_price': edge.award_price,
            'availability': edge.availability,
            'is_direct': 1 if edge.is_direct else 0,
            'has_transfer': 0 if edge.is_direct else 1,
            'airline_rank': self._get_airline_rank(edge.airline.iata),
            'fare_class_value': self._get_fare_class_value(edge.fare_class.class_code),
            'is_premium': 1 if edge.fare_class.class_code in ['F', 'J', 'P'] else 0,
            'is_economy': 1 if edge.fare_class.class_code in ['Y', 'M', 'H'] else 0,
            'is_business': 1 if edge.fare_class.class_code in ['C', 'D', 'I'] else 0
        }

    def _get_airline_rank(self, airline_iata: str) -> float:
        """Get airline quality rank (0-1)."""
        # In production, this would come from a pre-trained model
        airline_ranks = {
            'AA': 0.85, 'DL': 0.90, 'UA': 0.82, 'BA': 0.88,
            'LH': 0.92, 'AF': 0.87, 'JL': 0.85, 'NH': 0.83,
            'EK': 0.95, 'QR': 0.93, 'SQ': 0.94, 'CX': 0.91
        }
        return airline_ranks.get(airline_iata, 0.5)

    def _get_fare_class_value(self, class_code: str) -> float:
        """Get fare class value multiplier."""
        values = {
            'F': 5.0, 'J': 4.5, 'P': 4.0, 'C': 3.5, 'D': 3.0,
            'I': 2.5, 'A': 2.0, 'Y': 1.0, 'M': 0.9, 'H': 0.8,
            'Q': 0.7, 'K': 0.6, 'L': 0.5, 'U': 0.4, 'T': 0.3
        }
        return values.get(class_code, 0.5)

    def _normalize_features(self, features_df: cudf.DataFrame) -> cudf.DataFrame:
        """Normalize features using GPU-accelerated scaler."""
        if HAS_GPU:
            return self._feature_scaler.fit_transform(features_df)
        else:
            # CPU normalization
            for col in features_df.columns:
                if col not in ['is_direct', 'has_transfer', 'is_premium', 'is_economy', 'is_business']:
                    features_df[col] = (features_df[col] - features_df[col].mean()) / (features_df[col].std() + 1e-8)
            return features_df

    def _reduce_dimensions(self, features: np.ndarray) -> np.ndarray:
        """Reduce dimensions using PCA."""
        if HAS_GPU:
            return self._pca.fit_transform(features)
        else:
            return self._pca.fit_transform(features)

    def generate_route_embeddings(
        self,
        graph: AirportGraph,
        embedding_type: EmbeddingType = EmbeddingType.FULL_CONTEXT,
        batch_size: int = 10000
    ) -> Dict[str, np.ndarray]:
        """
        Generate vector embeddings for all routes in the graph.
        Returns dict mapping edge IDs to embeddings.
        """
        start_time = time.time()

        # Extract all edges
        edges = []
        edge_ids = []

        for src_idx, targets in graph._graph.items():
            for tgt_idx, edge_list in targets.items():
                for edge in edge_list:
                    edges.append(edge)
                    edge_ids.append(f"{edge.source.iata}_{edge.target.iata}_{edge.airline.iata}")

        if not edges:
            return {}

        # Extract features
        features = []
        for edge in edges:
            features.append(self._extract_route_features(edge))

        features_df = cudf.DataFrame(features) if HAS_GPU else pd.DataFrame(features)

        # Normalize
        features_normalized = self._normalize_features(features_df)

        # Reduce dimensions
        if HAS_GPU:
            features_array = features_normalized.to_numpy()
        else:
            features_array = features_normalized.values

        embeddings = self._reduce_dimensions(features_array)

        # Create result dict
        result = {}
        for i, edge_id in enumerate(edge_ids):
            result[edge_id] = embeddings[i]

        elapsed = time.time() - start_time
        print(f"Generated {len(edges)} route embeddings in {elapsed:.2f}s")

        return result

    def generate_airport_embeddings(
        self,
        graph: AirportGraph,
        route_embeddings: Dict[str, np.ndarray],
        embedding_type: EmbeddingType = EmbeddingType.FULL_CONTEXT
    ) -> Dict[str, np.ndarray]:
        """
        Generate embeddings for airports based on incoming/outgoing routes.
        """
        airport_embeddings = {}

        for airport in graph._airports.values():
            # Collect all route embeddings involving this airport
            incoming_edges = graph.get_routes_to(airport.iata)
            outgoing_edges = graph.get_routes_from(airport.iata)

            all_edges = incoming_edges + outgoing_edges
            edge_ids = [f"{e.source.iata}_{e.target.iata}_{e.airline.iata}" for e in all_edges]

            # Average the route embeddings
            if edge_ids:
                embedding_sum = np.zeros(self.embedding_dim)
                for edge_id in edge_ids:
                    if edge_id in route_embeddings:
                        embedding_sum += route_embeddings[edge_id]

                avg_embedding = embedding_sum / len(edge_ids)
                airport_embeddings[airport.iata] = avg_embedding
            else:
                # Default embedding for airports with no routes
                airport_embeddings[airport.iata] = np.random.randn(self.embedding_dim) * 0.1

        return airport_embeddings

    def generate_airline_embeddings(
        self,
        graph: AirportGraph,
        route_embeddings: Dict[str, np.ndarray]
    ) -> Dict[str, np.ndarray]:
        """Generate embeddings for airlines based on their routes."""
        airline_embeddings = {}

        for airline in graph._airlines.values():
            # Find all routes for this airline
            airline_edges = []
            for src_idx, targets in graph._graph.items():
                for tgt_idx, edge_list in targets.items():
                    for edge in edge_list:
                        if edge.airline.iata == airline.iata:
                            airline_edges.append(edge)

            if airline_edges:
                embedding_sum = np.zeros(self.embedding_dim)
                for edge in airline_edges:
                    edge_id = f"{edge.source.iata}_{edge.target.iata}_{edge.airline.iata}"
                    if edge_id in route_embeddings:
                        embedding_sum += route_embeddings[edge_id]

                avg_embedding = embedding_sum / len(airline_edges)
                airline_embeddings[airline.iata] = avg_embedding
            else:
                airline_embeddings[airline.iata] = np.random.randn(self.embedding_dim) * 0.1

        return airline_embeddings

    def compute_route_similarity(
        self,
        embedding1: np.ndarray,
        embedding2: np.ndarray,
        method: str = 'cosine'
    ) -> float:
        """Compute similarity between two route embeddings."""
        if method == 'cosine':
            if HAS_GPU:
                return cuml.metrics.pairwise.cosine_similarity(
                    embedding1.reshape(1, -1),
                    embedding2.reshape(1, -1)
                )[0][0]
            else:
                from sklearn.metrics.pairwise import cosine_similarity
                return cosine_similarity(
                    embedding1.reshape(1, -1),
                    embedding2.reshape(1, -1)
                )[0][0]
        elif method == 'euclidean':
            return 1.0 / (1.0 + np.linalg.norm(embedding1 - embedding2))
        else:
            raise ValueError(f"Unknown similarity method: {method}")

    def find_similar_routes(
        self,
        query_embedding: np.ndarray,
        route_embeddings: Dict[str, np.ndarray],
        top_k: int = 10
    ) -> List[Tuple[str, float]]:
        """Find most similar routes to a query embedding."""
        similarities = []

        for edge_id, embedding in route_embeddings.items():
            sim = self.compute_route_similarity(query_embedding, embedding)
            similarities.append((edge_id, sim))

        # Sort by similarity (descending)
        similarities.sort(key=lambda x: x[1], reverse=True)
        return similarities[:top_k]

    def save_embeddings(self, embeddings: Dict[str, np.ndarray], path: Path) -> None:
        """Save embeddings to disk."""
        data = {
            'embedding_dim': self.embedding_dim,
            'embeddings': {
                edge_id: embedding.tolist()
                for edge_id, embedding in embeddings.items()
            }
        }

        with open(path, 'w') as f:
            json.dump(data, f)

    def load_embeddings(self, path: Path) -> Dict[str, np.ndarray]:
        """Load embeddings from disk."""
        with open(path, 'r') as f:
            data = json.load(f)

        embeddings = {}
        for edge_id, embedding_list in data['embeddings'].items():
            embeddings[edge_id] = np.array(embedding_list)

        return embeddings
