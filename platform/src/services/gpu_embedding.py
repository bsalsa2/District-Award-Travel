import numpy as np
import torch
from typing import List, Tuple, Optional
from sentence_transformers import SentenceTransformer
from transformers import AutoTokenizer, AutoModel
import logging
from platform.src.config import settings

logger = logging.getLogger(__name__)

class GPUEmbeddingService:
    """
    High-performance GPU-accelerated semantic embedding service.
    Uses NVIDIA's embedding models for maximum throughput.
    """

    def __init__(self):
        self.device = "cuda" if torch.cuda.is_available() and settings.GPU_ENABLED else "cpu"
        self.batch_size = 1024  # Optimal batch size for GPU memory
        self.model = None
        self.tokenizer = None
        self._initialize_model()

    def _initialize_model(self):
        """Initialize the embedding model with optimal configuration."""
        try:
            logger.info(f"Initializing embedding model on device: {self.device}")

            # Use NVIDIA's optimized embedding model
            model_name = settings.EMBEDDING_MODEL

            if self.device == "cuda":
                # Load model with half precision for better performance
                self.model = AutoModel.from_pretrained(
                    model_name,
                    torch_dtype=torch.float16 if torch.cuda.is_available() else torch.float32,
                    trust_remote_code=True
                ).to(self.device)
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)
            else:
                # CPU fallback
                self.model = AutoModel.from_pretrained(model_name, trust_remote_code=True)
                self.tokenizer = AutoTokenizer.from_pretrained(model_name)

            logger.info(f"Model loaded successfully: {model_name}")
            logger.info(f"Model device: {self.model.device}")
            logger.info(f"Model dtype: {self.model.dtype}")

        except Exception as e:
            logger.error(f"Failed to initialize embedding model: {e}")
            raise

    def _preprocess_text(self, text: str) -> str:
        """Preprocess text for embedding."""
        # Clean and normalize text
        text = text.strip().lower()
        text = " ".join(text.split())  # Remove extra whitespace
        return text

    def embed_batch(self, texts: List[str]) -> Tuple[np.ndarray, List[str]]:
        """
        Generate embeddings for a batch of texts.

        Args:
            texts: List of text strings to embed

        Returns:
            Tuple of (embeddings, processed_texts)
        """
        if not texts:
            return np.array([]), []

        # Preprocess texts
        processed_texts = [self._preprocess_text(text) for text in texts]

        try:
            # Tokenize batch
            inputs = self.tokenizer(
                processed_texts,
                padding=True,
                truncation=True,
                max_length=settings.MAX_QUERY_LENGTH,
                return_tensors="pt"
            ).to(self.device)

            # Generate embeddings
            with torch.no_grad():
                outputs = self.model(**inputs)

            # Mean pooling
            embeddings = self._mean_pooling(outputs, inputs['attention_mask'])

            # Convert to numpy and normalize
            embeddings = embeddings.cpu().numpy()
            embeddings = embeddings / np.linalg.norm(embeddings, axis=1, keepdims=True)

            return embeddings, processed_texts

        except Exception as e:
            logger.error(f"Error generating embeddings: {e}")
            # Fallback to zero vectors
            return np.zeros((len(texts), settings.INDEX_DIMENSIONS)), processed_texts

    def _mean_pooling(self, model_output, attention_mask):
        """Mean pooling for sentence embeddings."""
        token_embeddings = model_output[0]  # First element contains all token embeddings
        input_mask_expanded = (
            attention_mask.unsqueeze(-1).expand(token_embeddings.size()).float()
        )
        return torch.sum(token_embeddings * input_mask_expanded, 1) / torch.clamp(
            input_mask_expanded.sum(1), min=1e-9
        )

    def embed_single(self, text: str) -> np.ndarray:
        """Generate embedding for a single text."""
        embeddings, _ = self.embed_batch([text])
        return embeddings[0]

    def semantic_similarity(self, embedding1: np.ndarray, embedding2: np.ndarray) -> float:
        """Calculate cosine similarity between two embeddings."""
        return float(np.dot(embedding1, embedding2) / (
            np.linalg.norm(embedding1) * np.linalg.norm(embedding2)
        ))

    def batch_similarity_search(
        self,
        query_embedding: np.ndarray,
        candidate_embeddings: np.ndarray,
        top_k: int = settings.TOP_K_RESULTS
    ) -> List[Tuple[int, float]]:
        """
        Perform batch similarity search using optimized GPU operations.

        Args:
            query_embedding: Query embedding vector
            candidate_embeddings: Matrix of candidate embeddings
            top_k: Number of results to return

        Returns:
            List of (index, similarity_score) tuples
        """
        # Calculate cosine similarities using matrix operations
        similarities = np.dot(candidate_embeddings, query_embedding) / (
            np.linalg.norm(candidate_embeddings, axis=1) * np.linalg.norm(query_embedding)
        )

        # Get top k indices
        top_indices = np.argpartition(similarities, -top_k)[-top_k:]
        top_scores = similarities[top_indices]

        # Sort by score descending
        sorted_indices = top_indices[np.argsort(-top_scores)]
        sorted_scores = top_scores[np.argsort(-top_scores)]

        return list(zip(sorted_indices.tolist(), sorted_scores.tolist()))

# Global instance
embedding_service = GPUEmbeddingService()
