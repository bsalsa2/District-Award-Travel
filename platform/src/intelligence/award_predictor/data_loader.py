"""
Award Prediction Data Loader
Handles data loading, preprocessing, and augmentation for the deep learning model.
Supports distributed training and GPU acceleration.
"""

import os
import logging
import numpy as np
import pandas as pd
import torch
from torch.utils.data import Dataset, DataLoader, DistributedSampler
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.model_selection import train_test_split
from sklearn.compose import ColumnTransformer
from sklearn.pipeline import Pipeline
from sklearn.impute import SimpleImputer
from typing import Tuple, Dict, Any
import pyarrow.parquet as pq
import pyarrow as pa
from .config import CONFIG

# Set up logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

class AwardDataset(Dataset):
    """
    PyTorch Dataset for award prediction data.
    Handles feature extraction and preprocessing.
    """

    def __init__(self, data: pd.DataFrame, config: Dict[str, Any], mode: str = "train"):
        self.config = config
        self.mode = mode
        self.data = data

        # Preprocess data
        self._preprocess_data()

        # Extract features and labels
        self.features = self._extract_features()
        self.labels = self._extract_labels()

        logger.info(f"Dataset initialized with {len(self)} samples")

    def _preprocess_data(self):
        """Handle missing values and basic preprocessing."""
        # Impute missing values
        numeric_imputer = SimpleImputer(strategy='median')
        categorical_imputer = SimpleImputer(strategy='most_frequent')

        # Create preprocessing pipeline
        numeric_transformer = Pipeline(steps=[
            ('imputer', numeric_imputer),
            ('scaler', StandardScaler())
        ])

        categorical_transformer = Pipeline(steps=[
            ('imputer', categorical_imputer),
            ('onehot', OneHotEncoder(handle_unknown='ignore', sparse_output=False))
        ])

        preprocessor = ColumnTransformer(
            transformers=[
                ('num', numeric_transformer, self.config['data'].numeric_columns),
                ('cat', categorical_transformer, self.config['data'].categorical_columns)
            ])

        # Apply preprocessing
        processed_data = preprocessor.fit_transform(self.data)

        # Convert to DataFrame for easier handling
        self.processed_data = pd.DataFrame(
            processed_data,
            columns=preprocessor.get_feature_names_out()
        )

        # Add sequence features if needed
        if self.config['data'].sequence_length > 0:
            self._create_sequences()

    def _create_sequences(self):
        """Create sequential data for transformer model."""
        # This is a simplified version - in production you'd want proper sequence creation
        # For now, we'll just pad/truncate to fixed length
        sequence_features = self.processed_data.values
        if len(sequence_features) > self.config['data'].sequence_length:
            sequence_features = sequence_features[:self.config['data'].sequence_length]
        else:
            padding = np.zeros((self.config['data'].sequence_length - len(sequence_features),
                               sequence_features.shape[1]))
            sequence_features = np.vstack([sequence_features, padding])

        self.sequence_features = sequence_features

    def _extract_features(self) -> torch.Tensor:
        """Extract feature tensor from processed data."""
        if self.config['data'].sequence_length > 0:
            features = torch.FloatTensor(self.sequence_features)
        else:
            features = torch.FloatTensor(self.processed_data.values)

        return features

    def _extract_labels(self) -> torch.Tensor:
        """Extract label tensor."""
        labels = torch.FloatTensor(self.data[self.config['data'].target_column].values)
        return labels.unsqueeze(1)

    def __len__(self) -> int:
        return len(self.labels)

    def __getitem__(self, idx: int) -> Tuple[torch.Tensor, torch.Tensor]:
        return self.features[idx], self.labels[idx]

    def get_feature_info(self) -> Dict[str, Any]:
        """Get information about features."""
        if self.config['data'].sequence_length > 0:
            return {
                "type": "sequence",
                "length": self.config['data'].sequence_length,
                "feature_dim": self.sequence_features.shape[1]
            }
        else:
            return {
                "type": "tabular",
                "num_features": self.processed_data.shape[1]
            }

class AwardDataModule:
    """
    Data module for award prediction.
    Handles data loading, splitting, and distributed training setup.
    """

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.train_dataset = None
        self.val_dataset = None
        self.test_dataset = None
        self.train_loader = None
        self.val_loader = None
        self.test_loader = None

        # Initialize scalers and encoders
        self.scaler = None
        self.encoder = None

    def load_data(self) -> None:
        """Load and preprocess data from parquet files."""
        logger.info("Loading data...")

        # Load raw data
        if os.path.exists(self.config['data'].processed_data_path):
            logger.info("Loading processed data from cache")
            data = pd.read_parquet(self.config['data'].processed_data_path)
        else:
            logger.info("Loading raw data")
            data = pd.read_parquet(self.config['data'].raw_data_path)

            # Save processed data for future use
            data.to_parquet(self.config['data'].processed_data_path)
            logger.info(f"Processed data saved to {self.config['data'].processed_data_path}")

        # Split data
        self._split_data(data)

    def _split_data(self, data: pd.DataFrame) -> None:
        """Split data into train, validation, and test sets."""
        logger.info("Splitting data...")

        # Stratified split based on target
        X = data.drop(columns=[self.config['data'].target_column])
        y = data[self.config['data'].target_column]

        X_train, X_temp, y_train, y_temp = train_test_split(
            X, y,
            test_size=self.config['data'].test_size + self.config['data'].val_size,
            random_state=self.config['data'].random_state,
            stratify=y
        )

        X_val, X_test, y_val, y_test = train_test_split(
            X_temp, y_temp,
            test_size=self.config['data'].test_size / (self.config['data'].test_size + self.config['data'].val_size),
            random_state=self.config['data'].random_state,
            stratify=y_temp
        )

        # Create DataFrames
        train_data = X_train.copy()
        train_data[self.config['data'].target_column] = y_train

        val_data = X_val.copy()
        val_data[self.config['data'].target_column] = y_val

        test_data = X_test.copy()
        test_data[self.config['data'].target_column] = y_test

        # Save splits
        train_data.to_parquet(self.config['training'].train_data_path)
        val_data.to_parquet(self.config['training'].val_data_path)
        test_data.to_parquet(self.config['training'].test_data_path)

        logger.info(f"Data split complete: {len(train_data)} train, {len(val_data)} val, {len(test_data)} test")

    def setup(self) -> None:
        """Setup datasets and data loaders."""
        logger.info("Setting up datasets...")

        # Load split data
        train_df = pd.read_parquet(self.config['training'].train_data_path)
        val_df = pd.read_parquet(self.config['training'].val_data_path)
        test_df = pd.read_parquet(self.config['training'].test_data_path)

        # Create datasets
        self.train_dataset = AwardDataset(train_df, self.config, mode="train")
        self.val_dataset = AwardDataset(val_df, self.config, mode="val")
        self.test_dataset = AwardDataset(test_df, self.config, mode="test")

        logger.info("Datasets created successfully")

    def create_dataloaders(self, distributed: bool = False) -> None:
        """Create data loaders for training, validation, and testing."""
        logger.info("Creating data loaders...")

        # Create distributed sampler if needed
        train_sampler = None
        if distributed and self.config['training'].distributed:
            train_sampler = DistributedSampler(self.train_dataset)

        # Create data loaders
        self.train_loader = DataLoader(
            self.train_dataset,
            batch_size=self.config['training'].batch_size,
            shuffle=(train_sampler is None),
            sampler=train_sampler,
            num_workers=min(4, os.cpu_count()),
            pin_memory=True,
            persistent_workers=True
        )

        self.val_loader = DataLoader(
            self.val_dataset,
            batch_size=self.config['training'].batch_size * 2,
            shuffle=False,
            num_workers=min(4, os.cpu_count()),
            pin_memory=True,
            persistent_workers=True
        )

        self.test_loader = DataLoader(
            self.test_dataset,
            batch_size=self.config['training'].batch_size * 2,
            shuffle=False,
            num_workers=min(4, os.cpu_count()),
            pin_memory=True,
            persistent_workers=True
        )

        logger.info(f"Data loaders created: {len(self.train_loader)} train batches, {len(self.val_loader)} val batches")

    def get_feature_info(self) -> Dict[str, Any]:
        """Get information about dataset features."""
        return self.train_dataset.get_feature_info()

    def get_data_distribution(self) -> Dict[str, Any]:
        """Get distribution of target variable."""
        train_counts = self.train_dataset.data[self.config['data'].target_column].value_counts(normalize=True)
        val_counts = self.val_dataset.data[self.config['data'].target_column].value_counts(normalize=True)
        test_counts = self.test_dataset.data[self.config['data'].target_column].value_counts(normalize=True)

        return {
            "train": train_counts.to_dict(),
            "val": val_counts.to_dict(),
            "test": test_counts.to_dict()
        }

# Utility functions
def load_dataset_from_parquet(file_path: str) -> pd.DataFrame:
    """Load dataset from parquet file."""
    return pd.read_parquet(file_path)

def save_dataset_to_parquet(data: pd.DataFrame, file_path: str) -> None:
    """Save dataset to parquet file."""
    data.to_parquet(file_path)

def create_data_pipeline(config: Dict[str, Any]) -> AwardDataModule:
    """Create complete data pipeline."""
    data_module = AwardDataModule(config)
    data_module.load_data()
    data_module.setup()
    data_module.create_dataloaders()
    return data_module
