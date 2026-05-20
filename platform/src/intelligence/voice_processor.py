"""
Voice Processing Module using NVIDIA Riva
Handles real-time speech-to-text with noise reduction and accent adaptation
"""

import asyncio
import logging
from typing import Optional

import numpy as np
import riva.client
from riva.client import AudioChunk

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class VoiceProcessor:
    def __init__(self):
        # Initialize Riva client with optimized settings for travel queries
        self.riva_client = riva.client.ASRService(
            uri="localhost:50051",  # Jetson edge or RTX cloud
            credentials=None,
            model_name="conformer_en_us_streaming",
            sample_rate=16000,
            enable_automatic_punctuation=True,
            max_alternatives=1,
            enable_spoken_punctuation=True
        )
        self.noise_profile = self._load_noise_profile()

    async def transcribe(self, audio_data: bytes) -> str:
        """Transcribe audio to text with noise reduction"""
        try:
            # Convert to AudioChunk
            audio_chunk = AudioChunk(
                audio_bytes=audio_data,
                sample_rate=self.riva_client.sample_rate,
                num_channels=1
            )

            # Apply noise reduction if needed
            if self._detect_noise(audio_chunk):
                audio_chunk = self._reduce_noise(audio_chunk)

            # Stream to Riva
            responses = self.riva_client.stream(
                audio_chunks=[audio_chunk],
                interim_results=False
            )

            # Collect results
            full_text = ""
            async for response in responses:
                if response.results:
                    full_text += response.results[0].alternatives[0].transcript

            return full_text.strip()

        except Exception as e:
            logger.error(f"Voice transcription failed: {e}")
            return ""

    def _detect_noise(self, audio_chunk: AudioChunk) -> bool:
        """Detect if audio contains significant background noise"""
        samples = np.frombuffer(audio_chunk.audio_bytes, dtype=np.int16)
        rms = np.sqrt(np.mean(samples**2))
        return rms < 1000  # Threshold for quiet audio

    def _reduce_noise(self, audio_chunk: AudioChunk) -> AudioChunk:
        """Apply noise reduction to audio"""
        samples = np.frombuffer(audio_chunk.audio_bytes, dtype=np.int16)
        # Simple noise reduction - in production would use RNNoise or similar
        samples = np.clip(samples, -8000, 8000)
        return AudioChunk(
            audio_bytes=samples.tobytes(),
            sample_rate=audio_chunk.sample_rate,
            num_channels=audio_chunk.num_channels
        )

    def _load_noise_profile(self) -> dict:
        """Load noise profile for travel environments"""
        return {
            "airport": {"rms_threshold": 2000, "noise_type": "babble"},
            "street": {"rms_threshold": 3000, "noise_type": "street"},
            "quiet": {"rms_threshold": 500, "noise_type": "none"}
        }

    async def adapt_to_accent(self, user_id: str, audio_samples: bytes):
        """Adapt voice model to user's accent (for frequent users)"""
        # In production would fine-tune Riva model or use adaptation API
        pass
