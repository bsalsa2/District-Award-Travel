import numpy as np
import onnxruntime as ort
from typing import List, Dict, Any
import time
import logging
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
from threading import Lock

from platform.src.schemas import ModelInput, ModelOutput
from platform.src.config import Config

logger = logging.getLogger(__name__)

class StreamingMLEngine:
    """
    High-performance streaming ML engine using ONNX Runtime with GPU acceleration.
    Designed for sub-second latency with batch processing capabilities.
    """

    def __init__(self, config: Config):
        self.config = config
        self.model_path = config.ml.model_path
        self.batch_size = config.ml.inference_batch_size
        self.gpu_device = config.ml.gpu_device
        self.max_latency = config.ml.max_latency_ms

        # Initialize ONNX Runtime session with optimized settings
        self._init_onnx_session()

        # Thread-safe components
        self.input_queue = Queue(maxsize=config.pipeline.max_events_per_second // 10)
        self.output_queue = Queue(maxsize=config.pipeline.max_events_per_second // 10)
        self.lock = Lock()
        self.warmup_complete = False

        # Performance tracking
        self.metrics = {
            'total_inferences': 0,
            'total_latency': 0.0,
            'batch_sizes': [],
            'last_warmup_time': 0.0
        }

        # Start processing threads
        self.executor = ThreadPoolExecutor(max_workers=4)
        self._start_processing()

    def _init_onnx_session(self):
        """Initialize ONNX Runtime session with GPU acceleration and optimized execution"""
        try:
            # Configure execution providers
            providers = ['CPUExecutionProvider']

            if self.config.pipeline.enable_gpu_direct:
                try:
                    providers.insert(0, 'CUDAExecutionProvider')
                    logger.info(f"GPU acceleration enabled with device: {self.gpu_device}")
                except Exception as e:
                    logger.warning(f"GPU acceleration failed: {e}. Falling back to CPU.")
                    providers = ['CPUExecutionProvider']

            # Session options for maximum performance
            sess_options = ort.SessionOptions()
            sess_options.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
            sess_options.execution_mode = ort.ExecutionMode.ORT_SEQUENTIAL
            sess_options.intra_op_num_threads = 4
            sess_options.inter_op_num_threads = 2

            # Load model
            self.session = ort.InferenceSession(
                self.model_path,
                sess_options,
                providers=providers
            )

            # Get model input/output info
            self.input_name = self.session.get_inputs()[0].name
            self.output_name = self.session.get_outputs()[0].name

            logger.info(f"ML Engine initialized with model: {self.model_path}")
            logger.info(f"Execution providers: {self.session.get_providers()}")

        except Exception as e:
            logger.error(f"Failed to initialize ML engine: {e}")
            raise

    def _warmup(self):
        """Warm up the model with sample data to ensure consistent performance"""
        try:
            warmup_input = np.random.rand(1, 128).astype(np.float32)
            for _ in range(self.config.ml.warmup_iterations):
                _ = self.session.run([self.output_name], {self.input_name: warmup_input})
            self.metrics['last_warmup_time'] = time.time()
            self.warmup_complete = True
            logger.info("ML model warmup completed")
        except Exception as e:
            logger.error(f"Model warmup failed: {e}")
            raise

    def _start_processing(self):
        """Start background processing threads"""
        # Start warmup in background
        self.executor.submit(self._warmup)

        # Start batch processor
        self.executor.submit(self._batch_processor)

    def _batch_processor(self):
        """Process batches of inputs with optimal batch size"""
        current_batch = []
        batch_start_time = time.time()

        while True:
            try:
                # Collect batch with timeout to prevent blocking
                while len(current_batch) < self.batch_size:
                    try:
                        item = self.input_queue.get(timeout=0.001)
                        current_batch.append(item)
                    except Exception:
                        break

                if not current_batch:
                    time.sleep(0.001)
                    continue

                # Process batch
                batch_input = self._prepare_batch_input(current_batch)
                start_time = time.time()

                try:
                    outputs = self.session.run(
                        [self.output_name],
                        {self.input_name: batch_input}
                    )

                    inference_latency = (time.time() - start_time) * 1000  # ms

                    # Process outputs
                    self._process_outputs(current_batch, outputs[0], inference_latency)

                    # Update metrics
                    with self.lock:
                        self.metrics['total_inferences'] += len(current_batch)
                        self.metrics['total_latency'] += inference_latency
                        self.metrics['batch_sizes'].append(len(current_batch))

                except Exception as e:
                    logger.error(f"Batch processing failed: {e}")
                    with self.lock:
                        self.metrics['error_count'] += len(current_batch)

                current_batch = []
                batch_start_time = time.time()

            except Exception as e:
                logger.error(f"Batch processor error: {e}")
                time.sleep(0.1)

    def _prepare_batch_input(self, batch: List[ModelInput]) -> np.ndarray:
        """Convert batch of ModelInput to numpy array for ONNX"""
        features = [item.features for item in batch]
        return np.array(features, dtype=np.float32)

    def _process_outputs(self, batch: List[ModelInput], outputs: np.ndarray, latency_ms: float):
        """Process model outputs and create ModelOutput objects"""
        for input_item, output in zip(batch, outputs):
            model_output = ModelOutput(
                predicted_price=float(output[0]),
                confidence=float(output[1]),
                feature_importance={f"feature_{i}": float(val) for i, val in enumerate(output[2:])},
                model_version=self.config.ml.model_path.split('/')[-1],
                inference_latency_ms=latency_ms / len(batch),  # Per-item latency
                metadata=input_item.metadata
            )
            self.output_queue.put(model_output)

    def predict(self, input_data: ModelInput) -> ModelOutput:
        """Synchronous prediction with caching"""
        if not self.warmup_complete:
            time.sleep(0.01)  # Wait for warmup

        start_time = time.time()
        self.input_queue.put(input_data)

        try:
            output = self.output_queue.get(timeout=self.max_latency / 1000)
            processing_time = (time.time() - start_time) * 1000

            with self.lock:
                self.metrics['total_inferences'] += 1
                self.metrics['total_latency'] += processing_time

            return output

        except Exception as e:
            logger.error(f"Prediction failed: {e}")
            with self.lock:
                self.metrics['error_count'] += 1
            raise

    def batch_predict(self, inputs: List[ModelInput]) -> List[ModelOutput]:
        """Batch prediction with optimized throughput"""
        if not self.warmup_complete:
            time.sleep(0.01)

        start_time = time.time()
        results = []

        for input_data in inputs:
            self.input_queue.put(input_data)

        # Collect results
        for _ in range(len(inputs)):
            try:
                output = self.output_queue.get(timeout=self.max_latency / 1000)
                results.append(output)
            except Exception as e:
                logger.error(f"Batch prediction failed: {e}")
                raise

        processing_time = (time.time() - start_time) * 1000

        with self.lock:
            self.metrics['total_inferences'] += len(inputs)
            self.metrics['total_latency'] += processing_time
            self.metrics['batch_sizes'].append(len(inputs))

        return results

    def get_metrics(self) -> Dict[str, Any]:
        """Get performance metrics"""
        with self.lock:
            avg_latency = self.metrics['total_latency'] / max(1, self.metrics['total_inferences'])
            avg_batch_size = np.mean(self.metrics['batch_sizes']) if self.metrics['batch_sizes'] else 0

            return {
                **self.metrics,
                'avg_latency_ms': avg_latency,
                'avg_batch_size': avg_batch_size,
                'throughput_per_sec': (1000 / avg_latency) * avg_batch_size if avg_latency > 0 else 0,
                'queue_sizes': {
                    'input_queue': self.input_queue.qsize(),
                    'output_queue': self.output_queue.qsize()
                },
                'timestamp': time.time()
            }

    def close(self):
        """Cleanup resources"""
        self.executor.shutdown(wait=True)
        self.session = None
        logger.info("ML Engine shutdown complete")
