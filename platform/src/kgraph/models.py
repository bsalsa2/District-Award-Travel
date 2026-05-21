"""
Knowledge Graph Models for Award Travel
Defines RDF models and data structures optimized for high-performance SPARQL queries.
"""

from typing import Dict, List, Optional, Set, Tuple
from dataclasses import dataclass
from datetime import datetime, date
from enum import Enum
import hashlib
from rdflib import URIRef, Literal, Graph, Namespace
from rdflib.namespace import RDF, RDFS, XSD, OWL

# Custom namespaces for award travel domain
AWARD = Namespace("https://schema.districtaward.travel/ontology/")
TRAVEL = Namespace("https://schema.districtaward.travel/travel/")
AIRLINE = Namespace("https://schema.districtaward.travel/airline/")
HOTEL = Namespace("https://schema.districtaward.travel/hotel/")
PARTNER = Namespace("https://schema.districtaward.travel/partner/")

class AwardType(Enum):
    """Enumeration of award types in the knowledge graph."""
    FLIGHT = "Flight"
    HOTEL = "Hotel"
    CAR_RENTAL = "CarRental"
    CRUISE = "Cruise"
    PACKAGE = "Package"

class CabinClass(Enum):
    """Enumeration of cabin classes."""
    ECONOMY = "Economy"
    PREMIUM_ECONOMY = "PremiumEconomy"
    BUSINESS = "Business"
    FIRST = "First"

class Currency(Enum):
    """Supported currencies."""
    USD = "USD"
    EUR = "EUR"
    GBP = "GBP"
    JPY = "JPY"
    CAD = "CAD"
    AUD = "AUD"

@dataclass(frozen=True, order=True)
class AwardKey:
    """Immutable key for award travel entries with natural ordering."""
    award_id: str
    award_type: AwardType
    partner_code: str

    def __hash__(self):
        return hash((self.award_id, self.award_type.value, self.partner_code))

@dataclass
class AwardTravel:
    """Core award travel data structure optimized for cache locality."""
    key: AwardKey
    title: str
    description: str
    award_type: AwardType
    partner_code: str
    partner_name: str
    currency: Currency
    face_value: float
    award_value: float
    redemption_cost: float
    available_from: date
    available_to: date
    booking_url: str
    image_url: Optional[str] = None
    tags: Set[str] = None
    metadata: Dict[str, str] = None

    def __post_init__(self):
        if self.tags is None:
            object.__setattr__(self, 'tags', set())
        if self.metadata is None:
            object.__setattr__(self, 'metadata', {})

    def to_rdf_triples(self) -> List[Tuple]:
        """Convert award travel to RDF triples for knowledge graph storage."""
        triples = []

        # Subject URI
        subject = URIRef(f"{TRAVEL[self.key.award_id]}")

        # Type assertion
        triples.append((subject, RDF.type, AWARD[self.key.award_type.value]))

        # Basic properties
        triples.append((subject, RDFS.label, Literal(self.title)))
        triples.append((subject, AWARD.description, Literal(self.description)))
        triples.append((subject, AWARD.partnerCode, Literal(self.partner_code)))
        triples.append((subject, AWARD.partnerName, Literal(self.partner_name)))
        triples.append((subject, AWARD.currency, Literal(self.currency.value)))
        triples.append((subject, AWARD.faceValue, Literal(self.face_value, datatype=XSD.float)))
        triples.append((subject, AWARD.awardValue, Literal(self.award_value, datatype=XSD.float)))
        triples.append((subject, AWARD.redemptionCost, Literal(self.redemption_cost, datatype=XSD.float)))
        triples.append((subject, AWARD.availableFrom, Literal(self.available_from.isoformat(), datatype=XSD.date)))
        triples.append((subject, AWARD.availableTo, Literal(self.available_to.isoformat(), datatype=XSD.date)))
        triples.append((subject, AWARD.bookingUrl, Literal(self.booking_url)))

        if self.image_url:
            triples.append((subject, AWARD.imageUrl, Literal(self.image_url)))

        # Tags as separate triples
        for tag in self.tags:
            triples.append((subject, AWARD.tag, Literal(tag)))

        # Metadata as separate triples
        for key, value in self.metadata.items():
            triples.append((subject, AWARD[f"meta_{key}"], Literal(value)))

        return triples

    @classmethod
    def from_rdf(cls, graph: Graph, subject: URIRef) -> Optional['AwardTravel']:
        """Parse AwardTravel from RDF graph."""
        try:
            award_id = str(subject).split('/')[-1]
            award_type_str = str(graph.value(subject, RDF.type)).split('/')[-1]
            award_type = AwardType(award_type_str)

            partner_code = str(graph.value(subject, AWARD.partnerCode))
            partner_name = str(graph.value(subject, AWARD.partnerName))
            title = str(graph.value(subject, RDFS.label))
            description = str(graph.value(subject, AWARD.description))
            currency = Currency(str(graph.value(subject, AWARD.currency)))
            face_value = float(graph.value(subject, AWARD.faceValue))
            award_value = float(graph.value(subject, AWARD.awardValue))
            redemption_cost = float(graph.value(subject, AWARD.redemptionCost))
            available_from = date.fromisoformat(str(graph.value(subject, AWARD.availableFrom)))
            available_to = date.fromisoformat(str(graph.value(subject, AWARD.availableTo)))
            booking_url = str(graph.value(subject, AWARD.bookingUrl))

            image_url = str(graph.value(subject, AWARD.imageUrl)) if graph.value(subject, AWARD.imageUrl) else None

            # Extract tags
            tags = {str(tag) for tag in graph.objects(subject, AWARD.tag)}

            # Extract metadata
            metadata = {}
            for triple in graph.triples((subject, None, None)):
                predicate = str(triple[1])
                if predicate.startswith(str(AWARD.meta_)):
                    key = predicate.replace(str(AWARD.meta_), '')
                    metadata[key] = str(triple[2])

            key = AwardKey(award_id, award_type, partner_code)

            return cls(
                key=key,
                title=title,
                description=description,
                award_type=award_type,
                partner_code=partner_code,
                partner_name=partner_name,
                currency=currency,
                face_value=face_value,
                award_value=award_value,
                redemption_cost=redemption_cost,
                available_from=available_from,
                available_to=available_to,
                booking_url=booking_url,
                image_url=image_url,
                tags=tags,
                metadata=metadata
            )
        except Exception:
            return None

class KnowledgeGraph:
    """High-performance knowledge graph wrapper optimized for award travel queries."""

    def __init__(self):
        self.graph = Graph()
        self._initialize_ontology()
        self._cache = {}  # Simple in-memory cache for frequently accessed awards
        self._cache_size = 10000

    def _initialize_ontology(self):
        """Initialize the ontology with award travel domain concepts."""
        # Add custom ontology triples
        self.graph.add((AWARD.Flight, RDFS.subClassOf, AWARD.Award))
        self.graph.add((AWARD.Hotel, RDFS.subClassOf, AWARD.Award))
        self.graph.add((AWARD.CarRental, RDFS.subClassOf, AWARD.Award))
        self.graph.add((AWARD.Cruise, RDFS.subClassOf, AWARD.Award))
        self.graph.add((AWARD.Package, RDFS.subClassOf, AWARD.Award))

        # Add properties
        self.graph.add((AWARD.partnerCode, RDFS.domain, AWARD.Award))
        self.graph.add((AWARD.partnerCode, RDFS.range, XSD.string))
        self.graph.add((AWARD.partnerName, RDFS.domain, AWARD.Award))
        self.graph.add((AWARD.partnerName, RDFS.range, XSD.string))
        self.graph.add((AWARD.redemptionCost, RDFS.domain, AWARD.Award))
        self.graph.add((AWARD.redemptionCost, RDFS.range, XSD.float))
        self.graph.add((AWARD.availableFrom, RDFS.domain, AWARD.Award))
        self.graph.add((AWARD.availableFrom, RDFS.range, XSD.date))
        self.graph.add((AWARD.availableTo, RDFS.domain, AWARD.Award))
        self.graph.add((AWARD.availableTo, RDFS.range, XSD.date))

    def add_award(self, award: AwardTravel):
        """Add an award to the knowledge graph with cache management."""
        triples = award.to_rdf_triples()
        self.graph.addN(triples)

        # Update cache
        cache_key = (award.key.award_id, award.key.award_type.value, award.key.partner_code)
        if len(self._cache) >= self._cache_size:
            self._cache.pop(next(iter(self._cache)))
        self._cache[cache_key] = award

    def get_award(self, award_id: str, award_type: AwardType, partner_code: str) -> Optional[AwardTravel]:
        """Retrieve an award from cache or knowledge graph."""
        cache_key = (award_id, award_type.value, partner_code)

        # Check cache first
        if cache_key in self._cache:
            return self._cache[cache_key]

        # Query knowledge graph
        subject = URIRef(f"{TRAVEL[award_id]}")
        award = AwardTravel.from_rdf(self.graph, subject)

        if award:
            self._cache[cache_key] = award
            return award

        return None

    def query_sparql(self, sparql_query: str) -> List[AwardTravel]:
        """Execute SPARQL query and return results as AwardTravel objects."""
        results = self.graph.query(sparql_query)

        awards = []
        for row in results:
            if isinstance(row, URIRef):
                award = self.get_award(
                    award_id=str(row).split('/')[-1],
                    award_type=AwardType.FLIGHT,  # Default, will be corrected in from_rdf
                    partner_code=""
                )
                if award:
                    awards.append(award)

        return awards

    def get_all_awards(self) -> List[AwardTravel]:
        """Retrieve all awards from the knowledge graph."""
        query = """
        SELECT ?award WHERE {
            ?award a ?type .
            FILTER(?type IN (aw:Award, aw:Flight, aw:Hotel, aw:CarRental, aw:Cruise, aw:Package))
        }
        """
        return self.query_sparql(query)

    def search_by_tags(self, tags: Set[str], limit: int = 100) -> List[AwardTravel]:
        """Search awards by tags with efficient query."""
        if not tags:
            return []

        # Build SPARQL query for tag search
        tag_filters = " ".join(f"?award aw:tag '{tag}' ." for tag in tags)

        query = f"""
        SELECT ?award WHERE {{
            {tag_filters}
        }}
        LIMIT {limit}
        """

        return self.query_sparql(query)

    def search_by_date_range(self, start_date: date, end_date: date, limit: int = 100) -> List[AwardTravel]:
        """Search awards available within a date range."""
        query = f"""
        SELECT ?award WHERE {{
            ?award aw:availableFrom ?from .
            ?award aw:availableTo ?to .
            FILTER(?from <= "{end_date.isoformat()}"^^xsd:date)
            FILTER(?to >= "{start_date.isoformat()}"^^xsd:date)
        }}
        LIMIT {limit}
        """

        return self.query_sparql(query)

    def search_by_redemption_cost(self, max_cost: float, currency: Currency = Currency.USD, limit: int = 100) -> List[AwardTravel]:
        """Search awards by maximum redemption cost."""
        query = f"""
        SELECT ?award WHERE {{
            ?award aw:redemptionCost ?cost .
            ?award aw:currency "{currency.value}" .
            FILTER(?cost <= {max_cost})
        }}
        LIMIT {limit}
        """

        return self.query_sparql(query)

    def search_by_value_ratio(self, min_ratio: float = 0.5, limit: int = 100) -> List[AwardTravel]:
        """Search awards where award_value/face_value >= min_ratio."""
        query = f"""
        SELECT ?award WHERE {{
            ?award aw:awardValue ?awardValue .
            ?award aw:faceValue ?faceValue .
            ?award aw:currency ?currency .
            FILTER(?awardValue / ?faceValue >= {min_ratio})
        }}
        LIMIT {limit}
        """

        return self.query_sparql(query)

    def get_partner_awards(self, partner_code: str, limit: int = 100) -> List[AwardTravel]:
        """Get all awards from a specific partner."""
        query = f"""
        SELECT ?award WHERE {{
            ?award aw:partnerCode "{partner_code}" .
        }}
        LIMIT {limit}
        """

        return self.query_sparql(query)

    def get_award_count(self) -> int:
        """Get total number of awards in the knowledge graph."""
        return len(list(self.graph.subjects(RDF.type, AWARD.Award)))

    def clear(self):
        """Clear the knowledge graph."""
        self.graph = Graph()
        self._initialize_ontology()
        self._cache.clear()
