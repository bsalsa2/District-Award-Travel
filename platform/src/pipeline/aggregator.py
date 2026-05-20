import sqlite3
from typing import List, Dict, Any
from datetime import datetime

class AwardAggregator:
    """
    Award aggregator with deduplication, sorting, and caching.
    Optimized for high-throughput data processing.
    """

    def __init__(self, db_path: str):
        self.db_path = db_path

    def aggregate_and_cache(
        self,
        results: List[Dict[str, Any]],
        origin: str,
        destination: str,
        date: str
    ) -> List[Dict[str, Any]]:
        """
        Aggregate, deduplicate, sort, and cache award results.

        Args:
            results: Raw results from scrapers
            origin: Origin airport code
            destination: Destination airport code
            date: Date in YYYY-MM-DD format

        Returns:
            Processed and sorted results
        """
        if not results:
            return []

        # Deduplicate by flight number and cabin
        unique_results = self._deduplicate(results)

        # Sort by value (miles + taxes)
        sorted_results = self._sort_by_value(unique_results)

        # Cache results
        self._cache_results(sorted_results, origin, destination, date)

        return sorted_results

    def _deduplicate(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Deduplicate results by flight number and cabin."""
        seen = set()
        unique_results = []

        for result in results:
            key = (
                result["airline"],
                result["flight_number"],
                result["cabin"],
                result["origin"],
                result["destination"],
                result["date"]
            )

            if key not in seen:
                seen.add(key)
                unique_results.append(result)

        return unique_results

    def _sort_by_value(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Sort results by total cost (miles + taxes)."""
        return sorted(
            results,
            key=lambda x: x["miles_required"] + x["taxes_usd"]
        )

    def _cache_results(
        self,
        results: List[Dict[str, Any]],
        origin: str,
        destination: str,
        date: str
    ) -> None:
        """Cache results in SQLite database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        # Use transaction for bulk insert
        try:
            cursor.execute("BEGIN TRANSACTION")

            # Delete old results for this route/date
            cursor.execute("""
            DELETE FROM award_searches
            WHERE origin = ? AND destination = ? AND date = ?
            """, (origin, destination, date))

            # Insert new results
            for result in results:
                cursor.execute("""
                INSERT OR IGNORE INTO award_searches
                (airline, flight_number, origin, destination, date, cabin,
                 miles_required, taxes_usd, available_seats)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """, (
                    result["airline"],
                    result["flight_number"],
                    result["origin"],
                    result["destination"],
                    result["date"],
                    result["cabin"],
                    result["miles_required"],
                    result["taxes_usd"],
                    result["available_seats"]
                ))

            conn.commit()
        except Exception as e:
            conn.rollback()
            raise e
        finally:
            conn.close()

    def get_cached_results(
        self,
        origin: str,
        destination: str,
        date: str
    ) -> List[Dict[str, Any]]:
        """Retrieve cached results from database."""
        conn = sqlite3.connect(self.db_path)
        cursor = conn.cursor()

        cursor.execute("""
        SELECT
            airline,
            flight_number,
            origin,
            destination,
            date,
            cabin,
            miles_required,
            taxes_usd,
            available_seats
        FROM award_searches
        WHERE origin = ? AND destination = ? AND date = ?
        ORDER BY miles_required ASC
        """, (origin, destination, date))

        columns = [col[0] for col in cursor.description]
        results = [dict(zip(columns, row)) for row in cursor.fetchall()]

        conn.close()
        return results
