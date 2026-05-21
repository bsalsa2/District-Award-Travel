"""
Award Prediction Model Configuration
Handles all hyperparameters, paths, and environment settings for the deep learning model.
"""

import os
from dataclasses import dataclass
from typing import List, Dict, Any
import torch

@dataclass
class TrainingConfig:
    # Model architecture
    model_name: str = "award_transformer_v1"
    hidden_size: int = 512
    num_hidden_layers: int = 6
    num_attention_heads: int = 8
    intermediate_size: int = 2048
    hidden_dropout_prob: float = 0.1
    attention_probs_dropout_prob: float = 0.1

    # Training parameters
    learning_rate: float = 3e-4
    weight_decay: float = 0.01
    batch_size: int = 256
    gradient_accumulation_steps: int = 4
    max_epochs: int = 100
    warmup_steps: int = 1000
    max_seq_length: int = 512

    # Optimization
    use_fp16: bool = True
    gradient_clip_val: float = 1.0
    adam_epsilon: float = 1e-8

    # Data
    train_data_path: str = "/data/award_train.parquet"
    val_data_path: str = "/data/award_val.parquet"
    test_data_path: str = "/data/award_test.parquet"
    cache_dir: str = "/data/cache"

    # Hardware
    use_tensor_cores: bool = True
    num_gpus: int = torch.cuda.device_count()
    device: str = "cuda" if torch.cuda.is_available() else "cpu"

    # Logging and monitoring
    log_dir: str = "/logs/award_predictor"
    checkpoint_dir: str = "/checkpoints/award_predictor"
    tensorboard_dir: str = "/logs/tensorboard"

    # Early stopping
    patience: int = 5
    min_delta: float = 0.001

    # Distributed training
    distributed: bool = False
    backend: str = "nccl"
    init_method: str = "env://"

    def __post_init__(self):
        # Create directories if they don't exist
        os.makedirs(self.cache_dir, exist_ok=True)
        os.makedirs(self.log_dir, exist_ok=True)
        os.makedirs(self.checkpoint_dir, exist_ok=True)
        os.makedirs(self.tensorboard_dir, exist_ok=True)

        # Set device
        self.device = torch.device(self.device)

        # Adjust batch size based on number of GPUs
        if self.num_gpus > 1:
            self.batch_size = self.batch_size * self.num_gpus

@dataclass
class ModelConfig:
    # Input features
    num_embedding_features: int = 128
    num_numeric_features: int = 10
    num_categorical_features: int = 50

    # Output
    num_classes: int = 2  # binary classification: award available or not
    output_size: int = 1

    # Embeddings
    max_sequence_length: int = 512
    embedding_dropout: float = 0.1

    # Transformer
    num_layers: int = 6
    num_heads: int = 8
    head_size: int = 64
    mlp_ratio: float = 4.0

@dataclass
class DataConfig:
    # Data paths
    raw_data_path: str = "/data/raw/award_data.parquet"
    processed_data_path: str = "/data/processed/award_data.parquet"

    # Feature engineering
    categorical_columns: List[str] = None
    numeric_columns: List[str] = None
    target_column: str = "award_available"

    # Preprocessing
    test_size: float = 0.2
    val_size: float = 0.1
    random_state: int = 42

    # Augmentation
    sequence_length: int = 256
    mask_probability: float = 0.15

    def __post_init__(self):
        if self.categorical_columns is None:
            self.categorical_columns = [
                "airline", "departure_airport", "arrival_airport",
                "cabin_class", "fare_basis", "ticket_type"
            ]
        if self.numeric_columns is None:
            self.numeric_columns = [
                "fare_amount", "tax_amount", "distance",
                "departure_hour", "departure_day_of_week",
                "booking_advance_days", "seats_available",
                "mileage_balance", "redemption_value",
                "partner_airline"
            ]

@dataclass
class ServingConfig:
    # Model serving
    model_path: str = "/models/award_predictor_v1.pt"
    max_batch_size: int = 1024
    max_latency: float = 0.1  # seconds
    num_workers: int = 4

    # API
    host: str = "0.0.0.0"
    port: int = 8001
    workers: int = 4

    # Monitoring
    metrics_port: int = 9091

@dataclass
class EvaluationConfig:
    # Metrics
    threshold: float = 0.5
    top_k: int = 5

    # Evaluation paths
    results_dir: str = "/results/award_predictor"
    report_path: str = "/results/award_predictor/report.json"

    def __post_init__(self):
        os.makedirs(self.results_dir, exist_ok=True)

# Global configuration
CONFIG = {
    "training": TrainingConfig(),
    "model": ModelConfig(),
    "data": DataConfig(),
    "serving": ServingConfig(),
    "evaluation": EvaluationConfig()
}
