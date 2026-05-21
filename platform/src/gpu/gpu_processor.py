import numpy as np
import cupy as cp
from typing import List, Dict, Tuple
import logging
from time import perf_counter
from ..config import config

logger = logging.getLogger(__name__)

class GPUQueryProcessor:
    """
    High-performance GPU-accelerated query processor for award searches.
    Uses CuPy for GPU acceleration and implements optimized algorithms for:
    - Vectorized similarity search
    - Range queries
    - Sorting and ranking
    - Parallel filtering
    """

    def __init__(self):
        self.initialized = False
        self._initialize_gpu()

    def _initialize_gpu(self):
        """Initialize GPU resources and data structures"""
        try:
            # Check GPU availability
            if not cp.cuda.runtime.getDeviceCount():
                logger.warning("No GPU devices found. Falling back to CPU.")
                self.use_gpu = False
                return

            self.use_gpu = config.USE_GPU_ACCELERATION
            if not self.use_gpu:
                logger.info("GPU acceleration disabled by config.")
                return

            # Set device
            self.device = cp.cuda.Device(0)
            self.device.use()

            # Initialize data structures
            self.feature_matrix = None
            self.index = None
            self.query_cache = {}

            self.initialized = True
            logger.info("GPU query processor initialized successfully.")
        except Exception as e:
            logger.error(f"Failed to initialize GPU processor: {e}")
            self.use_gpu = False

    def _ensure_initialized(self):
        """Ensure GPU processor is initialized"""
        if not self.initialized:
            self._initialize_gpu()
            if not self.initialized:
                raise RuntimeError("GPU processor not available")

    def _to_gpu_array(self, data: np.ndarray) -> cp.ndarray:
        """Move numpy array to GPU"""
        return cp.asarray(data, dtype=cp.float32)

    def _to_cpu_array(self, data: cp.ndarray) -> np.ndarray:
        """Move GPU array to CPU"""
        return cp.asnumpy(data)

    def build_index(self, features: List[Dict[str, float]]):
        """
        Build GPU-accelerated index for fast similarity search.
        Features should be a list of dictionaries with numeric values.
        """
        self._ensure_initialized()

        if not self.use_gpu:
            return

        try:
            logger.info(f"Building GPU index with {len(features)} records...")

            # Convert features to numpy array
            feature_names = list(features[0].keys())
            data = np.array([[f[name] for name in feature_names] for f in features],
                          dtype=np.float32)

            # Move to GPU
            gpu_data = self._to_gpu_array(data)

            # Build index (using L2 distance for similarity)
            # In a real implementation, we'd use a proper GPU-accelerated index like FAISS
            # For this example, we'll use brute-force with GPU acceleration
            self.feature_names = feature_names
            self.feature_matrix = gpu_data

            logger.info("GPU index built successfully.")
        except Exception as e:
            logger.error(f"Failed to build GPU index: {e}")
            self.use_gpu = False

    def gpu_range_query(self, feature_name: str, min_val: float, max_val: float,
                       limit: int = 100) -> List[int]:
        """
        Perform a range query on GPU.
        Returns indices of records within the specified range.
        """
        self._ensure_initialized()

        if not self.use_gpu or self.feature_matrix is None:
            return []

        try:
            # Find column index
            col_idx = self.feature_names.index(feature_name)
            if col_idx == -1:
                return []

            # Extract column and perform range query
            column = self.feature_matrix[:, col_idx]
            mask = (column >= min_val) & (column <= max_val)

            # Get indices
            indices = cp.where(mask)[0]

            # Limit results
            if limit > 0 and len(indices) > limit:
                # Sort by the feature value and take top results
                sorted_indices = cp.argsort(column[indices])
                indices = indices[sorted_indices[:limit]]

            return self._to_cpu_array(indices).tolist()
        except Exception as e:
            logger.error(f"GPU range query failed: {e}")
            return []

    def gpu_k_nearest_neighbors(self, query_features: Dict[str, float],
                               k: int = 10) -> Tuple[List[int], List[float]]:
        """
        Find k nearest neighbors using GPU acceleration.
        Returns (indices, distances) of nearest neighbors.
        """
        self._ensure_initialized()

        if not self.use_gpu or self.feature_matrix is None:
            return [], []

        try:
            # Convert query to array
            query_array = np.array([query_features[name] for name in self.feature_names],
                                 dtype=np.float32)
            gpu_query = self._to_gpu_array(query_array)

            # Calculate distances (L2 norm)
            diff = self.feature_matrix - gpu_query
            distances = cp.sqrt(cp.sum(diff ** 2, axis=1))

            # Get k smallest distances
            nearest_indices = cp.argsort(distances)[:k]
            nearest_distances = distances[nearest_indices]

            return (self._to_cpu_array(nearest_indices).tolist(),
                   self._to_cpu_array(nearest_distances).tolist())
        except Exception as e:
            logger.error(f"GPU k-NN search failed: {e}")
            return [], []

    def gpu_sort_by_feature(self, feature_name: str, descending: bool = False,
                           limit: int = 100) -> List[int]:
        """
        Sort records by a feature on GPU.
        """
        self._ensure_initialized()

        if not self.use_gpu or self.feature_matrix is None:
            return []

        try:
            col_idx = self.feature_names.index(feature_name)
            if col_idx == -1:
                return []

            column = self.feature_matrix[:, col_idx]
            if descending:
                sorted_indices = cp.argsort(-column)
            else:
                sorted_indices = cp.argsort(column)

            if limit > 0 and len(sorted_indices) > limit:
                sorted_indices = sorted_indices[:limit]

            return self._to_cpu_array(sorted_indices).tolist()
        except Exception as e:
            logger.error(f"GPU sort failed: {e}")
            return []

    def parallel_filter(self, conditions: Dict[str, Tuple[float, float]]) -> List[int]:
        """
        Apply multiple filter conditions in parallel on GPU.
        conditions: {feature_name: (min_val, max_val)}
        """
        self._ensure_initialized()

        if not self.use_gpu or self.feature_matrix is None:
            return []

        try:
            # Start with all indices
            mask = cp.ones(len(self.feature_matrix), dtype=bool)

            # Apply each condition
            for feature_name, (min_val, max_val) in conditions.items():
                col_idx = self.feature_names.index(feature_name)
                if col_idx == -1:
                    continue

                column = self.feature_matrix[:, col_idx]
                feature_mask = (column >= min_val) & (column <= max_val)
                mask = mask & feature_mask

            # Get matching indices
            indices = cp.where(mask)[0]
            return self._to_cpu_array(indices).tolist()
        except Exception as e:
            logger.error(f"GPU parallel filter failed: {e}")
            return []

    def batch_process_queries(self, queries: List[Dict], processor_func, batch_size: int = 1000):
        """
        Process queries in batches on GPU for maximum throughput.
        """
        self._ensure_initialized()

        if not self.use_gpu:
            return [processor_func(q) for q in queries]

        results = []
        for i in range(0, len(queries), batch_size):
            batch = queries[i:i + batch_size]
            batch_results = self._batch_process_gpu(batch, processor_func)
            results.extend(batch_results)

        return results

    def _batch_process_gpu(self, batch: List[Dict], processor_func):
        """
        Internal method to process a batch of queries on GPU.
        """
        try:
            # Convert batch to GPU array
            batch_size = len(batch)
            batch_array = np.zeros((batch_size, len(self.feature_names)), dtype=np.float32)

            for i, query in enumerate(batch):
                for j, feature_name in enumerate(self.feature_names):
                    batch_array[i, j] = query.get(feature_name, 0.0)

            gpu_batch = self._to_gpu_array(batch_array)

            # Process on GPU (this would be customized per processor_func)
            # For example, if processor_func is gpu_k_nearest_neighbors:
            # We'd implement a batched version

            # For now, fall back to CPU for batch processing
            return [processor_func(q) for q in batch]
        except Exception as e:
            logger.error(f"Batch processing failed: {e}")
            return [processor_func(q) for q in batch]

# Singleton instance
gpu_processor = GPUQueryProcessor()
