"""
Award Prediction Transformer Model
PyTorch implementation of a transformer-based model for predicting award availability.
Uses NVIDIA Tensor Cores for acceleration.
"""

import torch
import torch.nn as nn
import torch.nn.functional as F
from torch import Tensor
from typing import Tuple, Optional, Dict, Any
import math
from .config import CONFIG

class PositionalEncoding(nn.Module):
    """
    Positional encoding for transformer models.
    Adds positional information to input embeddings.
    """

    def __init__(self, d_model: int, max_len: int = 5000):
        super().__init__()
        self.d_model = d_model
        self.max_len = max_len

        position = torch.arange(max_len).unsqueeze(1)
        div_term = torch.exp(torch.arange(0, d_model, 2) * (-math.log(10000.0) / d_model))
        pe = torch.zeros(max_len, d_model)
        pe[:, 0::2] = torch.sin(position * div_term)
        pe[:, 1::2] = torch.cos(position * div_term)
        self.register_buffer('pe', pe)

    def forward(self, x: Tensor) -> Tensor:
        """
        Args:
            x: Tensor, shape [batch_size, seq_len, embedding_dim]
        Returns:
            x with positional encoding added
        """
        x = x * math.sqrt(self.d_model)
        seq_len = x.size(1)
        x = x + self.pe[:seq_len]
        return x

class MultiHeadAttention(nn.Module):
    """
    Multi-head attention layer with optional Tensor Core acceleration.
    """

    def __init__(self, embed_dim: int, num_heads: int, dropout: float = 0.1):
        super().__init__()
        self.embed_dim = embed_dim
        self.num_heads = num_heads
        self.head_dim = embed_dim // num_heads

        assert self.head_dim * num_heads == embed_dim, "embed_dim must be divisible by num_heads"

        self.qkv_proj = nn.Linear(embed_dim, 3 * embed_dim)
        self.out_proj = nn.Linear(embed_dim, embed_dim)
        self.dropout = nn.Dropout(dropout)

        # Use FlashAttention if available (requires PyTorch 2.0+)
        self.use_flash = hasattr(torch.nn.functional, 'scaled_dot_product_attention')
        if self.use_flash:
            self.sdpa = torch.nn.functional.scaled_dot_product_attention

    def forward(self, x: Tensor, mask: Optional[Tensor] = None) -> Tensor:
        batch_size, seq_length, embed_dim = x.size()

        # Project to Q, K, V
        qkv = self.qkv_proj(x)
        q, k, v = qkv.chunk(3, dim=-1)

        # Reshape for multi-head attention
        q = q.view(batch_size, seq_length, self.num_heads, self.head_dim).transpose(1, 2)
        k = k.view(batch_size, seq_length, self.num_heads, self.head_dim).transpose(1, 2)
        v = v.view(batch_size, seq_length, self.num_heads, self.head_dim).transpose(1, 2)

        if self.use_flash:
            # Use FlashAttention for better performance on Tensor Cores
            attn_output = self.sdpa(
                q, k, v,
                attn_mask=mask,
                dropout_p=self.dropout.p if self.training else 0.0
            )
        else:
            # Standard attention computation
            attn_scores = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.head_dim)

            if mask is not None:
                attn_scores = attn_scores.masked_fill(mask == 0, float('-inf'))

            attn_weights = F.softmax(attn_scores, dim=-1)
            attn_weights = self.dropout(attn_weights)
            attn_output = torch.matmul(attn_weights, v)

        # Concatenate heads and project
        attn_output = attn_output.transpose(1, 2).contiguous()
        attn_output = attn_output.view(batch_size, seq_length, embed_dim)
        output = self.out_proj(attn_output)

        return output

class TransformerBlock(nn.Module):
    """
    Transformer block with multi-head attention and feed-forward network.
    """

    def __init__(self, embed_dim: int, num_heads: int, mlp_ratio: float = 4.0, dropout: float = 0.1):
        super().__init__()
        self.norm1 = nn.LayerNorm(embed_dim)
        self.attn = MultiHeadAttention(embed_dim, num_heads, dropout)
        self.norm2 = nn.LayerNorm(embed_dim)
        self.mlp = nn.Sequential(
            nn.Linear(embed_dim, int(embed_dim * mlp_ratio)),
            nn.GELU(),
            nn.Dropout(dropout),
            nn.Linear(int(embed_dim * mlp_ratio), embed_dim),
            nn.Dropout(dropout)
        )

    def forward(self, x: Tensor, mask: Optional[Tensor] = None) -> Tensor:
        # Self-attention
        residual = x
        x = self.norm1(x)
        x = self.attn(x, mask)
        x = residual + x

        # Feed-forward network
        residual = x
        x = self.norm2(x)
        x = self.mlp(x)
        x = residual + x

        return x

class AwardTransformer(nn.Module):
    """
    Transformer-based model for award prediction.
    Handles both sequential and tabular data.
    """

    def __init__(self, config: Dict[str, Any]):
        super().__init__()
        self.config = config
        self.model_config = config['model']

        # Input embedding layer
        self.embedding = self._create_embedding_layer()

        # Positional encoding
        self.pos_encoder = PositionalEncoding(
            d_model=self.model_config['hidden_size'],
            max_len=self.model_config['max_sequence_length']
        )

        # Transformer blocks
        self.transformer_blocks = nn.ModuleList([
            TransformerBlock(
                embed_dim=self.model_config['hidden_size'],
                num_heads=self.model_config['num_heads'],
                mlp_ratio=self.model_config['mlp_ratio'],
                dropout=self.model_config['hidden_dropout_prob']
            )
            for _ in range(self.model_config['num_layers'])
        ])

        # Output layer
        self.norm = nn.LayerNorm(self.model_config['hidden_size'])
        self.output = nn.Linear(self.model_config['hidden_size'], self.model_config['output_size'])

        # Initialize weights
        self._init_weights()

        # Move to device
        self.to(config['training'].device)

    def _create_embedding_layer(self) -> nn.Module:
        """Create embedding layer for input features."""
        # For simplicity, we'll use a linear projection
        # In production, you might want separate embeddings for different feature types
        return nn.Linear(
            in_features=self.config['data'].num_numeric_features +
                      self.config['data'].num_categorical_features,
            out_features=self.model_config['hidden_size']
        )

    def _init_weights(self):
        """Initialize model weights."""
        for m in self.modules():
            if isinstance(m, nn.Linear):
                nn.init.xavier_normal_(m.weight)
                if m.bias is not None:
                    nn.init.constant_(m.bias, 0)
            elif isinstance(m, nn.LayerNorm):
                nn.init.constant_(m.weight, 1.0)
                nn.init.constant_(m.bias, 0.0)

    def forward(self, x: Tensor, mask: Optional[Tensor] = None) -> Tensor:
        """
        Forward pass of the model.

        Args:
            x: Input tensor of shape [batch_size, seq_len, num_features]
            mask: Optional mask tensor of shape [batch_size, seq_len]

        Returns:
            Output tensor of shape [batch_size, output_size]
        """
        # Embed input
        x = self.embedding(x)

        # Add positional encoding
        x = self.pos_encoder(x)

        # Apply transformer blocks
        for block in self.transformer_blocks:
            x = block(x, mask)

        # Final normalization and output
        x = self.norm(x)
        x = x.mean(dim=1)  # Average over sequence length
        x = self.output(x)

        return torch.sigmoid(x)

    def predict(self, x: Tensor, mask: Optional[Tensor] = None) -> Tuple[Tensor, Tensor]:
        """
        Predict award availability with probabilities.

        Args:
            x: Input tensor
            mask: Optional mask tensor

        Returns:
            Tuple of (predictions, probabilities)
        """
        with torch.no_grad():
            probs = self.forward(x, mask)
            preds = (probs > self.config['evaluation'].threshold).float()
        return preds, probs

    def get_attention_weights(self, x: Tensor, mask: Optional[Tensor] = None) -> Tensor:
        """
        Get attention weights from the last transformer block.

        Args:
            x: Input tensor
            mask: Optional mask tensor

        Returns:
            Attention weights tensor
        """
        # Embed input
        x = self.embedding(x)
        x = self.pos_encoder(x)

        # Apply all but last transformer block
        for block in self.transformer_blocks[:-1]:
            x = block(x, mask)

        # Get attention from last block
        x = self.transformer_blocks[-1].norm1(x)
        qkv = self.transformer_blocks[-1].attn.qkv_proj(x)
        q, k, v = qkv.chunk(3, dim=-1)

        # Reshape for attention
        q = q.view(x.size(0), x.size(1), self.model_config['num_heads'], self.model_config['head_size']).transpose(1, 2)
        k = k.view(x.size(0), x.size(1), self.model_config['num_heads'], self.model_config['head_size']).transpose(1, 2)

        # Compute attention weights
        attn_weights = torch.matmul(q, k.transpose(-2, -1)) / math.sqrt(self.model_config['head_size'])
        if mask is not None:
            attn_weights = attn_weights.masked_fill(mask.unsqueeze(1).unsqueeze(2) == 0, float('-inf'))
        attn_weights = F.softmax(attn_weights, dim=-1)

        return attn_weights

class AwardModelFactory:
    """
    Factory for creating and managing award prediction models.
    """

    @staticmethod
    def create_model(config: Dict[str, Any]) -> AwardTransformer:
        """Create a new award prediction model."""
        return AwardTransformer(config)

    @staticmethod
    def load_model(model_path: str, config: Dict[str, Any]) -> AwardTransformer:
        """Load a saved model."""
        model = AwardTransformer(config)
        state_dict = torch.load(model_path, map_location=config['training'].device)
        model.load_state_dict(state_dict)
        model.eval()
        return model

    @staticmethod
    def save_model(model: AwardTransformer, model_path: str) -> None:
        """Save a model to disk."""
        torch.save(model.state_dict(), model_path)

# Utility functions for model optimization
def enable_tensor_cores(model: AwardTransformer) -> None:
    """
    Enable mixed precision training with Tensor Cores.
    """
    try:
        from torch.cuda.amp import GradScaler, autocast

        # Enable automatic mixed precision
        model.amp_enabled = True
        model.scaler = GradScaler()

        # Enable cuDNN auto-tuner for better performance
        torch.backends.cudnn.benchmark = True
        torch.backends.cudnn.deterministic = False

        print("Tensor Cores and mixed precision enabled")
    except ImportError:
        print("AMP not available, running in standard precision")
        model.amp_enabled = False

def optimize_model(model: AwardTransformer) -> None:
    """
    Apply various optimizations to the model.
    """
    # Enable cuDNN optimizations
    torch.backends.cudnn.enabled = True
    torch.backends.cudnn.benchmark = True

    # Enable TF32 for Ampere GPUs (Tensor Cores)
    if torch.cuda.is_available() and torch.cuda.get_device_capability()[0] >= 8:
        torch.backends.cuda.matmul.allow_tf32 = True
        torch.backends.cudnn.allow_tf32 = True
        print("TF32 enabled for Tensor Core acceleration")

    # Enable gradient checkpointing for memory efficiency
    for block in model.transformer_blocks:
        block.checkpoint = True
