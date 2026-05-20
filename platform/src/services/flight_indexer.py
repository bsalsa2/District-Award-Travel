import asyncio
import json
import logging
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Set
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from sqlalchemy import or_, and_, between
from platform.src.models.base import FlightOffer, SemanticIndex
from platform.src.services.gpu_embedding import embedding_service
from platform.src.config import settings, COMFORT_LEVELS, SEAT_TYPES
import numpy as np
from collections import defaultdict
import hashlib

logger = logging.getLogger(__name__)

class FlightIndexer:
    """
    High-performance flight data indexer with semantic search capabilities.
    Uses GPU-accelerated embeddings for fast indexing and retrieval.
    """

    def __init__(self, db_session: AsyncSession):
        self.db_session = db_session
        self.flight_cache = {}  # In-memory cache for active flights
        self.semantic_cache = {}  # In-memory semantic index cache
        self.index_lock = asyncio.Lock()

    async def index_flight_offer(self, flight_data: Dict) -> bool:
        """
        Index a single flight offer with semantic understanding.

        Args:
            flight_data: Flight offer data dictionary

        Returns:
            bool: True if indexed successfully
        """
        try:
            # Create semantic text for this flight
            semantic_text = self._generate_semantic_text(flight_data)

            # Generate embedding
            embedding = embedding_service.embed_single(semantic_text)

            # Store in semantic index
            semantic_entry = SemanticIndex(
                text=semantic_text,
                embedding=json.dumps(embedding.tolist()),
                metadata={
                    "flight_offer_id": flight_data.get("offer_id"),
                    "airline": flight_data.get("airline"),
                    "departure_airport": flight_data.get("departure_airport"),
                    "arrival_airport": flight_data.get("arrival_airport"),
                    "cabin_class": flight_data.get("cabin_class"),
                    "price": flight_data.get("price"),
                    "is_award": flight_data.get("is_award", False),
                    "award_price": flight_data.get("award_price"),
                    "alliance": flight_data.get("alliance"),
                    "departure_time": flight_data.get("departure_time"),
                    "arrival_time": flight_data.get("arrival_time")
                },
                expires_at=datetime.utcnow() + timedelta(days=30)
            )

            self.db_session.add(semantic_entry)

            # Update flight cache
            cache_key = self._generate_cache_key(flight_data)
            self.flight_cache[cache_key] = flight_data

            logger.debug(f"Indexed flight offer: {flight_data.get('offer_id')}")
            return True

        except Exception as e:
            logger.error(f"Error indexing flight offer: {e}")
            return False

    async def batch_index_flight_offers(self, flight_data_list: List[Dict]) -> int:
        """
        Batch index multiple flight offers for maximum throughput.

        Args:
            flight_data_list: List of flight offer data dictionaries

        Returns:
            int: Number of successfully indexed offers
        """
        if not flight_data_list:
            return 0

        indexed_count = 0

        try:
            # Generate semantic texts and embeddings in batches
            semantic_texts = [self._generate_semantic_text(data) for data in flight_data_list]
            embeddings, _ = embedding_service.embed_batch(semantic_texts)

            # Prepare semantic entries
            semantic_entries = []
            for i, flight_data in enumerate(flight_data_list):
                semantic_text = semantic_texts[i]
                embedding = embeddings[i]

                semantic_entry = SemanticIndex(
                    text=semantic_text,
                    embedding=json.dumps(embedding.tolist()),
                    metadata={
                        "flight_offer_id": flight_data.get("offer_id"),
                        "airline": flight_data.get("airline"),
                        "departure_airport": flight_data.get("departure_airport"),
                        "arrival_airport": flight_data.get("arrival_airport"),
                        "cabin_class": flight_data.get("cabin_class"),
                        "price": flight_data.get("price"),
                        "is_award": flight_data.get("is_award", False),
                        "award_price": flight_data.get("award_price"),
                        "alliance": flight_data.get("alliance"),
                        "departure_time": flight_data.get("departure_time"),
                        "arrival_time": flight_data.get("arrival_time")
                    },
                    expires_at=datetime.utcnow() + timedelta(days=30)
                )
                semantic_entries.append(semantic_entry)

                # Update flight cache
                cache_key = self._generate_cache_key(flight_data)
                self.flight_cache[cache_key] = flight_data

            # Bulk insert
            self.db_session.add_all(semantic_entries)
            indexed_count = len(flight_data_list)

            logger.info(f"Batch indexed {indexed_count} flight offers")
            return indexed_count

        except Exception as e:
            logger.error(f"Error in batch indexing: {e}")
            return 0

    async def rebuild_semantic_index(self, flight_offers: List[FlightOffer]) -> int:
        """
        Rebuild the entire semantic index from flight offers.

        Args:
            flight_offers: List of FlightOffer model instances

        Returns:
            int: Number of indexed entries
        """
        indexed_count = 0

        try:
            # Clear existing index
            await self.db_session.execute(SemanticIndex.__table__.delete())

            # Process in batches for memory efficiency
            batch_size = 1000
            for i in range(0, len(flight_offers), batch_size):
                batch = flight_offers[i:i + batch_size]

                # Generate semantic texts and embeddings
                semantic_texts = [self._generate_semantic_text_from_offer(offer) for offer in batch]
                embeddings, _ = embedding_service.embed_batch(semantic_texts)

                # Create semantic entries
                semantic_entries = []
                for j, offer in enumerate(batch):
                    semantic_text = semantic_texts[j]
                    embedding = embeddings[j]

                    semantic_entry = SemanticIndex(
                        text=semantic_text,
                        embedding=json.dumps(embedding.tolist()),
                        metadata={
                            "flight_offer_id": offer.offer_id,
                            "airline": offer.airline,
                            "departure_airport": offer.departure_airport,
                            "arrival_airport": offer.arrival_airport,
                            "cabin_class": offer.cabin_class,
                            "price": offer.price,
                            "is_award": offer.is_award,
                            "award_price": offer.award_price,
                            "alliance": offer.alliance,
                            "departure_time": offer.departure_time.isoformat(),
                            "arrival_time": offer.arrival_time.isoformat()
                        },
                        expires_at=datetime.utcnow() + timedelta(days=30)
                    )
                    semantic_entries.append(semantic_entry)

                # Bulk insert
                self.db_session.add_all(semantic_entries)
                indexed_count += len(batch)

                logger.info(f"Processed batch {i//batch_size + 1}: {len(batch)} entries")

            logger.info(f"Completed semantic index rebuild: {indexed_count} entries")
            return indexed_count

        except Exception as e:
            logger.error(f"Error rebuilding semantic index: {e}")
            raise

    async def semantic_search(
        self,
        query: str,
        top_k: int = settings.TOP_K_RESULTS,
        min_similarity: float = settings.SEMANTIC_SIMILARITY_THRESHOLD
    ) -> List[Dict]:
        """
        Perform semantic search on flight offers.

        Args:
            query: User query text
            top_k: Number of results to return
            min_similarity: Minimum similarity threshold

        Returns:
            List of matching flight offers with scores
        """
        try:
            # Generate query embedding
            query_embedding = embedding_service.embed_single(query)

            # Query semantic index for similar entries
            stmt = select(SemanticIndex).order_by(SemanticIndex.text.ilike(f"%{query}%"))

            result = await self.db_session.execute(stmt)
            semantic_entries = result.scalars().all()

            # Calculate similarities
            candidate_embeddings = []
            metadata_list = []

            for entry in semantic_entries:
                try:
                    embedding = np.array(json.loads(entry.embedding))
                    candidate_embeddings.append(embedding)
                    metadata_list.append(entry.metadata)
                except Exception as e:
                    logger.warning(f"Error parsing embedding: {e}")
                    continue

            if not candidate_embeddings:
                return []

            # Batch similarity search
            similarities = embedding_service.batch_similarity_search(
                query_embedding,
                np.array(candidate_embeddings),
                top_k * 2  # Get more candidates to filter
            )

            # Filter by similarity threshold and get flight offers
            results = []
            seen_offer_ids = set()

            for idx, score in similarities:
                if score >= min_similarity and idx < len(metadata_list):
                    metadata = metadata_list[idx]
                    offer_id = metadata.get("flight_offer_id")

                    if offer_id and offer_id not in seen_offer_ids:
                        seen_offer_ids.add(offer_id)

                        # Get full flight offer details
                        flight_offer = await self._get_flight_offer(offer_id)
                        if flight_offer:
                            results.append({
                                "offer": flight_offer,
                                "score": float(score),
                                "metadata": metadata
                            })

                            if len(results) >= top_k:
                                break

            # Sort by score descending
            results.sort(key=lambda x: x["score"], reverse=True)

            return results

        except Exception as e:
            logger.error(f"Error in semantic search: {e}")
            return []

    async def hybrid_search(
        self,
        query: str,
        departure_airport: Optional[str] = None,
        arrival_airport: Optional[str] = None,
        departure_date: Optional[datetime] = None,
        cabin_class: Optional[str] = None,
        max_price: Optional[float] = None,
        min_similarity: float = settings.SEMANTIC_SIMILARITY_THRESHOLD,
        top_k: int = settings.TOP_K_RESULTS
    ) -> List[Dict]:
        """
        Perform hybrid search combining semantic understanding with structured filters.

        Args:
            query: User query text
            departure_airport: Departure airport filter
            arrival_airport: Arrival airport filter
            departure_date: Departure date filter
            cabin_class: Cabin class filter
            max_price: Maximum price filter
            min_similarity: Minimum similarity threshold
            top_k: Number of results to return

        Returns:
            List of matching flight offers with scores
        """
        # First perform semantic search
        semantic_results = await self.semantic_search(query, top_k * 3, min_similarity)

        # Apply structured filters
        filtered_results = []
        for result in semantic_results:
            offer = result["offer"]
            metadata = result["metadata"]

            # Apply filters
            if departure_airport and offer.departure_airport != departure_airport:
                continue
            if arrival_airport and offer.arrival_airport != arrival_airport:
                continue
            if departure_date and offer.departure_time.date() != departure_date.date():
                continue
            if cabin_class and offer.cabin_class != cabin_class:
                continue
            if max_price and offer.price > max_price:
                continue

            # Apply additional filters from metadata
            if metadata.get("is_award") and max_price and metadata.get("award_price", 0) > max_price:
                continue

            filtered_results.append({
                **result,
                "offer": offer
            })

            if len(filtered_results) >= top_k:
                break

        return filtered_results

    async def _get_flight_offer(self, offer_id: str) -> Optional[FlightOffer]:
        """Get flight offer by ID with caching."""
        cache_key = f"flight_offer:{offer_id}"

        # Check cache first
        if cache_key in self.flight_cache:
            return self.flight_cache[cache_key]

        # Query database
        stmt = select(FlightOffer).where(FlightOffer.offer_id == offer_id)
        result = await self.db_session.execute(stmt)
        flight_offer = result.scalar_one_or_none()

        if flight_offer:
            # Update cache
            self.flight_cache[cache_key] = flight_offer

        return flight_offer

    def _generate_semantic_text(self, flight_data: Dict) -> str:
        """Generate semantic text for flight offer."""
        departure_airport = flight_data.get("departure_airport", "")
        arrival_airport = flight_data.get("arrival_airport", "")
        airline = flight_data.get("airline", "")
        cabin_class = flight_data.get("cabin_class", "economy")
        price = flight_data.get("price", 0)
        is_award = flight_data.get("is_award", False)
        alliance = flight_data.get("alliance", "")
        departure_time = flight_data.get("departure_time", "")
        arrival_time = flight_data.get("arrival_time", "")
        duration = flight_data.get("duration_minutes", 0)
        layovers = flight_data.get("layovers", 0)

        # Build comprehensive semantic text
        semantic_parts = [
            f"Flight from {departure_airport} to {arrival_airport}",
            f"Operated by {airline}",
            f"Cabin class: {cabin_class}",
            f"Price: ${price:.2f}",
            f"Duration: {duration} minutes",
            f"Layovers: {layovers}",
            f"Alliance: {alliance}" if alliance else "",
            "Award flight" if is_award else "Paid flight",
            f"Departure: {departure_time}",
            f"Arrival: {arrival_time}"
        ]

        return " ".join([part for part in semantic_parts if part])

    def _generate_semantic_text_from_offer(self, offer: FlightOffer) -> str:
        """Generate semantic text from FlightOffer model."""
        semantic_parts = [
            f"Flight from {offer.departure_airport} to {offer.arrival_airport}",
            f"Operated by {offer.airline}",
            f"Cabin class: {offer.cabin_class}",
            f"Price: ${offer.price:.2f}",
            f"Duration: {offer.duration_minutes} minutes",
            f"Layovers: {offer.layovers}",
            f"Alliance: {offer.alliance}" if offer.alliance else "",
            "Award flight" if offer.is_award else "Paid flight",
            f"Departure: {offer.departure_time.isoformat()}",
            f"Arrival: {offer.arrival_time.isoformat()}"
        ]

        return " ".join([part for part in semantic_parts if part])

    def _generate_cache_key(self, flight_data: Dict) -> str:
        """Generate cache key for flight data."""
        key_parts = [
            flight_data.get("departure_airport", ""),
            flight_data.get("arrival_airport", ""),
            flight_data.get("departure_time", ""),
            flight_data.get("airline", ""),
            flight_data.get("cabin_class", "")
        ]
        return hashlib.md5("|".join(key_parts).encode()).hexdigest()
