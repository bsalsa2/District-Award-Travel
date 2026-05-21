"""
Knowledge Graph Serializers
RDF serialization and deserialization utilities optimized for award travel.
"""

from typing import Dict, List, Optional
from rdflib import Graph, URIRef, Literal, Namespace
from rdflib.namespace import RDF, RDFS, XSD
from rdflib.plugins.serializers import turtle, jsonld

from kgraph.models import AwardTravel, AwardType, Currency, KnowledgeGraph

class RDFSerializer:
    """Serializer for RDF data with multiple format support."""

    def __init__(self):
        self.default_graph = Graph()

    def serialize_to_turtle(self, kgraph: KnowledgeGraph) -> str:
        """Serialize knowledge graph to Turtle format."""
        return kgraph.graph.serialize(format='turtle').decode('utf-8')

    def serialize_to_jsonld(self, kgraph: KnowledgeGraph) -> Dict:
        """Serialize knowledge graph to JSON-LD format."""
        return kgraph.graph.serialize(format='json-ld', indent=2)

    def serialize_award_to_turtle(self, award: AwardTravel) -> str:
        """Serialize single award to Turtle format."""
        graph = Graph()
        triples = award.to_rdf_triples()
        graph.addN(triples)
        return graph.serialize(format='turtle').decode('utf-8')

    def deserialize_from_turtle(self, turtle_data: str) -> KnowledgeGraph:
        """Deserialize Turtle data into knowledge graph."""
        kgraph = KnowledgeGraph()
        kgraph.graph.parse(data=turtle_data, format='turtle')
        return kgraph

    def deserialize_from_jsonld(self, jsonld_data: Dict) -> KnowledgeGraph:
        """Deserialize JSON-LD data into knowledge graph."""
        kgraph = KnowledgeGraph()
        kgraph.graph.parse(data=jsonld_data, format='json-ld')
        return kgraph

    def award_to_dict(self, award: AwardTravel) -> Dict:
        """Convert award to dictionary for API responses."""
        return {
            'award_id': award.key.award_id,
            'type': award.award_type.value,
            'title': award.title,
            'description': award.description,
            'partner_code': award.partner_code,
            'partner_name': award.partner_name,
            'currency': award.currency.value,
            'face_value': award.face_value,
            'award_value': award.award_value,
            'redemption_cost': award.redemption_cost,
            'available_from': award.available_from.isoformat(),
            'available_to': award.available_to.isoformat(),
            'booking_url': award.booking_url,
            'image_url': award.image_url,
            'tags': list(award.tags),
            'metadata': award.metadata
        }

    def awards_to_dict_list(self, awards: List[AwardTravel]) -> List[Dict]:
        """Convert list of awards to list of dictionaries."""
        return [self.award_to_dict(award) for award in awards]

class SPARQLQueryBuilder:
    """Builder pattern for constructing SPARQL queries for award search."""

    def __init__(self):
        self._select = "?award"
        self._where = []
        self._filters = []
        self._order_by = None
        self._limit = 100
        self._offset = 0

    def select_awards(self):
        """Set the SELECT clause to return award URIs."""
        self._select = "?award"
        return self

    def select_award_details(self):
        """Set the SELECT clause to return detailed award information."""
        self._select = """
        ?award ?predicate ?object .
        FILTER(?predicate IN (
            aw:title, aw:description, aw:partnerCode, aw:partnerName,
            aw:currency, aw:faceValue, aw:awardValue, aw:redemptionCost,
            aw:availableFrom, aw:availableTo, aw:bookingUrl, aw:imageUrl
        ))
        """
        return self

    def filter_by_type(self, award_type: AwardType):
        """Filter by award type."""
        self._where.append(f"?award a aw:{award_type.value} .")
        return self

    def filter_by_partner(self, partner_code: str):
        """Filter by partner code."""
        self._where.append(f'?award aw:partnerCode "{partner_code}" .')
        return self

    def filter_by_currency(self, currency: Currency):
        """Filter by currency."""
        self._where.append(f'?award aw:currency "{currency.value}" .')
        return self

    def filter_by_date_range(self, start_date: str, end_date: str):
        """Filter by date range."""
        self._where.append(f'?award aw:availableFrom ?from .')
        self._where.append(f'?award aw:availableTo ?to .')
        self._filters.append(f'?from <= "{end_date}"^^xsd:date')
        self._filters.append(f'?to >= "{start_date}"^^xsd:date')
        return self

    def filter_by_redemption_cost(self, max_cost: float):
        """Filter by maximum redemption cost."""
        self._where.append('?award aw:redemptionCost ?cost .')
        self._filters.append(f'?cost <= {max_cost}')
        return self

    def filter_by_value_ratio(self, min_ratio: float):
        """Filter by minimum award value to face value ratio."""
        self._where.append('?award aw:awardValue ?awardValue .')
        self._where.append('?award aw:faceValue ?faceValue .')
        self._filters.append(f'?awardValue / ?faceValue >= {min_ratio}')
        return self

    def filter_by_tags(self, tags: List[str]):
        """Filter by tags."""
        for tag in tags:
            self._where.append(f'?award aw:tag "{tag}" .')
        return self

    def filter_by_text_search(self, search_term: str):
        """Filter by text search in title and description."""
        self._where.append(f'?award aw:title ?title .')
        self._where.append(f'?award aw:description ?description .')
        self._filters.append(f'CONTAINS(LCASE(?title), "{search_term.lower()}")')
        self._filters.append(f'CONTAINS(LCASE(?description), "{search_term.lower()}")')
        return self

    def order_by_redemption_cost(self, ascending: bool = True):
        """Order results by redemption cost."""
        direction = "ASC" if ascending else "DESC"
        self._order_by = f'(?cost {direction})'
        return self

    def order_by_value_ratio(self, ascending: bool = False):
        """Order results by value ratio (award_value/face_value)."""
        self._order_by = '(?awardValue/?faceValue DESC)'
        return self

    def limit(self, limit: int):
        """Set result limit."""
        self._limit = limit
        return self

    def offset(self, offset: int):
        """Set result offset."""
        self._offset = offset
        return self

    def build(self) -> str:
        """Build the final SPARQL query."""
        query_parts = []

        # SELECT clause
        query_parts.append(f"SELECT {self._select}")

        # WHERE clause
        query_parts.append("WHERE {")
        query_parts.extend(self._where)

        # Add filters
        if self._filters:
            query_parts.append("FILTER(")
            query_parts.append(" && ".join(self._filters))
            query_parts.append(")")

        query_parts.append("}")

        # ORDER BY clause
        if self._order_by:
            query_parts.append(f"ORDER BY {self._order_by}")

        # LIMIT and OFFSET
        query_parts.append(f"LIMIT {self._limit}")
        if self._offset > 0:
            query_parts.append(f"OFFSET {self._offset}")

        return "\n".join(query_parts)

class SPARQLResultParser:
    """Parse SPARQL query results into structured data."""

    @staticmethod
    def parse_sparql_results(results: List, kgraph: KnowledgeGraph) -> List[Dict]:
        """Parse SPARQL results into structured award data."""
        awards = []

        for row in results:
            if 'award' in row:
                award_uri = row['award']
                award = kgraph.get_award(
                    award_id=str(award_uri).split('/')[-1],
                    award_type=AwardType.FLIGHT,  # Will be corrected by from_rdf
                    partner_code=""
                )
                if award:
                    awards.append(RDFSerializer().award_to_dict(award))

        return awards

    @staticmethod
    def parse_detailed_results(results: List) -> List[Dict]:
        """Parse detailed SPARQL results where each row is a property."""
        awards_dict = {}

        for row in results:
            award_uri = str(row['award'])
            if award_uri not in awards_dict:
                awards_dict[award_uri] = {
                    'award_id': award_uri.split('/')[-1],
                    'properties': {}
                }

            predicate = str(row['predicate']).split('/')[-1]
            value = str(row['object'])

            # Handle different property types
            if predicate in ['faceValue', 'awardValue', 'redemptionCost']:
                awards_dict[award_uri]['properties'][predicate] = float(value)
            elif predicate in ['availableFrom', 'availableTo']:
                awards_dict[award_uri]['properties'][predicate] = value
            else:
                awards_dict[award_uri]['properties'][predicate] = value

        return list(awards_dict.values())
