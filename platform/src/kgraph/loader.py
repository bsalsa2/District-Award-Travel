"""
Knowledge Graph Data Loader
High-performance RDF data loader with batch processing and validation.
"""

import asyncio
import aiohttp
from typing import List, Dict, Optional
from datetime import datetime, date
from rdflib import URIRef, Literal, Graph
from rdflib.namespace import RDF, RDFS, XSD

from kgraph.models import AwardTravel, AwardKey, AwardType, Currency, KnowledgeGraph
from kgraph.serializers import RDFSerializer

class AwardDataLoader:
    """Asynchronous data loader for award travel knowledge graph."""

    def __init__(self, kgraph: KnowledgeGraph):
        self.kgraph = kgraph
        self.serializer = RDFSerializer()
        self.batch_size = 1000
        self.max_concurrent_requests = 20

    async def load_from_api(self, api_endpoint: str, api_key: str) -> int:
        """Load award data from REST API endpoint."""
        headers = {
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json"
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(api_endpoint, headers=headers) as response:
                if response.status != 200:
                    raise Exception(f"API request failed: {response.status}")

                data = await response.json()
                return await self.load_from_json(data)

    async def load_from_json(self, json_data: Dict) -> int:
        """Load award data from JSON structure."""
        awards = []

        # Process each award in the JSON data
        for item in json_data.get('awards', []):
            try:
                award = self._json_to_award(item)
                if award:
                    awards.append(award)
            except Exception as e:
                print(f"Error processing award: {e}")
                continue

        # Batch load into knowledge graph
        return self._batch_load_awards(awards)

    def _json_to_award(self, json_data: Dict) -> Optional[AwardTravel]:
        """Convert JSON award data to AwardTravel object."""
        try:
            award_type = AwardType(json_data.get('type', 'Flight'))

            key = AwardKey(
                award_id=json_data.get('id', ''),
                award_type=award_type,
                partner_code=json_data.get('partner_code', '')
            )

            return AwardTravel(
                key=key,
                title=json_data.get('title', ''),
                description=json_data.get('description', ''),
                award_type=award_type,
                partner_code=json_data.get('partner_code', ''),
                partner_name=json_data.get('partner_name', ''),
                currency=Currency(json_data.get('currency', 'USD')),
                face_value=float(json_data.get('face_value', 0)),
                award_value=float(json_data.get('award_value', 0)),
                redemption_cost=float(json_data.get('redemption_cost', 0)),
                available_from=date.fromisoformat(json_data.get('available_from', '2024-01-01')),
                available_to=date.fromisoformat(json_data.get('available_to', '2025-12-31')),
                booking_url=json_data.get('booking_url', ''),
                image_url=json_data.get('image_url'),
                tags=set(json_data.get('tags', [])),
                metadata=json_data.get('metadata', {})
            )
        except Exception as e:
            print(f"Error converting JSON to award: {e}")
            return None

    def _batch_load_awards(self, awards: List[AwardTravel]) -> int:
        """Load awards in batches for optimal performance."""
        count = 0

        for i in range(0, len(awards), self.batch_size):
            batch = awards[i:i + self.batch_size]

            for award in batch:
                self.kgraph.add_award(award)
                count += 1

        return count

    async def load_from_csv(self, file_path: str) -> int:
        """Load award data from CSV file."""
        import csv

        awards = []

        with open(file_path, 'r', encoding='utf-8') as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    award = self._csv_row_to_award(row)
                    if award:
                        awards.append(award)
                except Exception as e:
                    print(f"Error processing CSV row: {e}")
                    continue

        return self._batch_load_awards(awards)

    def _csv_row_to_award(self, row: Dict) -> Optional[AwardTravel]:
        """Convert CSV row to AwardTravel object."""
        try:
            award_type = AwardType(row.get('type', 'Flight'))

            key = AwardKey(
                award_id=row.get('id', ''),
                award_type=award_type,
                partner_code=row.get('partner_code', '')
            )

            return AwardTravel(
                key=key,
                title=row.get('title', ''),
                description=row.get('description', ''),
                award_type=award_type,
                partner_code=row.get('partner_code', ''),
                partner_name=row.get('partner_name', ''),
                currency=Currency(row.get('currency', 'USD')),
                face_value=float(row.get('face_value', 0)),
                award_value=float(row.get('award_value', 0)),
                redemption_cost=float(row.get('redemption_cost', 0)),
                available_from=date.fromisoformat(row.get('available_from', '2024-01-01')),
                available_to=date.fromisoformat(row.get('available_to', '2025-12-31')),
                booking_url=row.get('booking_url', ''),
                image_url=row.get('image_url'),
                tags=set(row.get('tags', '').split(',') if row.get('tags') else []),
                metadata={}
            )
        except Exception as e:
            print(f"Error converting CSV row to award: {e}")
            return None

    async def load_from_rdf_file(self, file_path: str) -> int:
        """Load award data from RDF file."""
        graph = Graph()
        graph.parse(file_path, format='turtle')

        # Extract awards from RDF graph
        awards = []
        for subject in graph.subjects(RDF.type, None):
            award = AwardTravel.from_rdf(graph, subject)
            if award:
                awards.append(award)

        return self._batch_load_awards(awards)

    async def load_from_multiple_sources(self, sources: List[Dict]) -> Dict[str, int]:
        """Load data from multiple sources concurrently."""
        tasks = []
        results = {}

        for source in sources:
            if source['type'] == 'api':
                task = asyncio.create_task(
                    self.load_from_api(source['endpoint'], source['api_key'])
                )
                tasks.append((source['name'], task))
            elif source['type'] == 'json':
                task = asyncio.create_task(
                    self.load_from_json(source['data'])
                )
                tasks.append((source['name'], task))
            elif source['type'] == 'csv':
                task = asyncio.create_task(
                    self.load_from_csv(source['path'])
                )
                tasks.append((source['name'], task))
            elif source['type'] == 'rdf':
                task = asyncio.create_task(
                    self.load_from_rdf_file(source['path'])
                )
                tasks.append((source['name'], task))

        # Execute tasks concurrently
        for name, task in tasks:
            results[name] = await task

        return results

class RDFDataValidator:
    """Validates RDF data before loading into knowledge graph."""

    @staticmethod
    def validate_award_graph(graph: Graph) -> bool:
        """Validate that award graph has required structure."""
        required_predicates = [
            'http://www.w3.org/2000/01/rdf-schema#label',
            'https://schema.districtaward.travel/ontology/partnerCode',
            'https://schema.districtaward.travel/ontology/partnerName',
            'https://schema.districtaward.travel/ontology/currency',
            'https://schema.districtaward.travel/ontology/faceValue',
            'https://schema.districtaward.travel/ontology/awardValue',
            'https://schema.districtaward.travel/ontology/redemptionCost',
            'https://schema.districtaward.travel/ontology/availableFrom',
            'https://schema.districtaward.travel/ontology/availableTo',
            'https://schema.districtaward.travel/ontology/bookingUrl'
        ]

        # Check if we have any awards
        award_count = len(list(graph.subjects(RDF.type, None)))
        if award_count == 0:
            return False

        # Check for required predicates
        for predicate in required_predicates:
            if not any(graph.predicates(subject=None, predicate=URIRef(predicate))):
                return False

        return True

    @staticmethod
    def validate_award_data(award: AwardTravel) -> bool:
        """Validate individual award data."""
        if not award.key.award_id:
            return False
        if award.redemption_cost < 0:
            return False
        if award.face_value <= 0:
            return False
        if award.available_from > award.available_to:
            return False
        return True
