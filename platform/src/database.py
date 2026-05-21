from neo4j import GraphDatabase
from platform.src.models import AirlineRoute, AwardAvailability, TransferBonus

class GraphDatabaseClient:
    def __init__(self, uri, auth):
        self.driver = GraphDatabase.driver(uri, auth=auth)

    def close(self):
        self.driver.close()

    def create_airline_route(self, airline_route: AirlineRoute):
        with self.driver.session() as session:
            session.write_transaction(self._create_airline_route, airline_route)

    def _create_airline_route(self, tx, airline_route: AirlineRoute):
        tx.run("CREATE (r:AirlineRoute {id: $id, airline: $airline, origin: $origin, destination: $destination, distance: $distance})",
               id=airline_route.id, airline=airline_route.airline, origin=airline_route.origin, destination=airline_route.destination, distance=airline_route.distance)

    def create_award_availability(self, award_availability: AwardAvailability):
        with self.driver.session() as session:
            session.write_transaction(self._create_award_availability, award_availability)

    def _create_award_availability(self, tx, award_availability: AwardAvailability):
        tx.run("CREATE (a:AwardAvailability {id: $id, airline: $airline, route_id: $route_id, availability: $availability})",
               id=award_availability.id, airline=award_availability.airline, route_id=award_availability.route_id, availability=award_availability.availability)

    def create_transfer_bonus(self, transfer_bonus: TransferBonus):
        with self.driver.session() as session:
            session.write_transaction(self._create_transfer_bonus, transfer_bonus)

    def _create_transfer_bonus(self, tx, transfer_bonus: TransferBonus):
        tx.run("CREATE (t:TransferBonus {id: $id, airline: $airline, route_id: $route_id, bonus: $bonus})",
               id=transfer_bonus.id, airline=transfer_bonus.airline, route_id=transfer_bonus.route_id, bonus=transfer_bonus.bonus)

    def query_award_search(self, origin: str, destination: str):
        with self.driver.session() as session:
            result = session.read_transaction(self._query_award_search, origin, destination)
            return result

    def _query_award_search(self, tx, origin: str, destination: str):
        result = tx.run("MATCH (r:AirlineRoute {origin: $origin, destination: $destination})-[:HAS_AWARD_AVAILABILITY]->(a:AwardAvailability) RETURN a",
                        origin=origin, destination=destination)
        return [record["a"] for record in result]
