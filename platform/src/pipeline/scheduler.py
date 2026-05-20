import asyncio
import logging
from typing import List, Dict, Any
from datetime import datetime, timedelta

logger = logging.getLogger(__name__)

class SearchScheduler:
    """
    Scheduler for running award searches automatically.
    Designed for high reliability and minimal resource usage.
    """

    def __init__(self, pipeline):
        self.pipeline = pipeline
        self._active_routes = self._load_active_routes()
        self._shutdown = False
        self._task = None

    def _load_active_routes(self) -> List[Dict[str, Any]]:
        """Load active client routes from configuration."""
        # In a real implementation, this would load from a database or config file
        # For now, return some sample routes
        return [
            {"origin": "JFK", "destination": "LAX", "date": "2026-06-15"},
            {"origin": "JFK", "destination": "LHR", "date": "2026-06-20"},
            {"origin": "LAX", "destination": "HND", "date": "2026-07-01"},
            {"origin": "SFO", "destination": "CDG", "date": "2026-07-10"},
        ]

    async def run_hourly_searches(self) -> None:
        """Run searches for all active routes every hour."""
        logger.info("Starting hourly award search scheduler")

        while not self._shutdown:
            try:
                start_time = datetime.now()
                logger.info(f"Running scheduled searches at {start_time}")

                # Run searches for all active routes
                tasks = []
                for route in self._active_routes:
                    task = asyncio.create_task(
                        self._search_route(route)
                    )
                    tasks.append(task)

                # Wait for all searches to complete
                await asyncio.gather(*tasks)

                # Calculate sleep time to maintain hourly schedule
                end_time = datetime.now()
                elapsed = (end_time - start_time).total_seconds()
                sleep_time = max(0, 3600 - elapsed)  # 3600 seconds = 1 hour

                logger.info(f"Completed scheduled searches in {elapsed:.2f}s, sleeping for {sleep_time:.2f}s")

                # Sleep until next hour
                await asyncio.sleep(sleep_time)

            except asyncio.CancelledError:
                logger.info("Scheduled searches cancelled")
                break
            except Exception as e:
                logger.error(f"Error in scheduled searches: {str(e)}")
                # Wait before retrying
                await asyncio.sleep(60)

    async def _search_route(self, route: Dict[str, Any]) -> None:
        """Search a single route."""
        try:
            logger.info(
                f"Searching {route['origin']}->{route['destination']} on {route['date']}"
            )
            results = await self.pipeline.search_route(
                route["origin"],
                route["destination"],
                route["date"]
            )

            if results:
                logger.info(
                    f"Found {len(results)} award options for "
                    f"{route['origin']}->{route['destination']} on {route['date']}"
                )
            else:
                logger.info(
                    f"No award options found for "
                    f"{route['origin']}->{route['destination']} on {route['date']}"
                )
        except Exception as e:
            logger.error(
                f"Error searching {route['origin']}->{route['destination']}: {str(e)}"
            )

    def close(self) -> None:
        """Clean up resources."""
        self._shutdown = True
        if self._task:
            self._task.cancel()
            try:
                if hasattr(self._task, 'result'):
                    self._task.result()
            except asyncio.CancelledError:
                pass
        logger.info("Search scheduler closed")
