import csv
from typing import Dict, List

class ValuationService:
    def __init__(self, csv_file: str):
        self.valuations = self.load_valuations(csv_file)

    def load_valuations(self, csv_file: str) -> Dict[str, float]:
        valuations = {}
        with open(csv_file, 'r') as f:
            reader = csv.DictReader(f)
            for row in reader:
                valuations[row['program']] = float(row['cents_per_point'])
        return valuations

    def get_all_valuations(self) -> Dict[str, float]:
        return self.valuations

    def get_valuation(self, program: str) -> float:
        return self.valuations.get(program, 0.0)

    def calculate_value(self, program: str, points: int) -> Dict[str, float]:
        cpp = self.get_valuation(program)
        total_usd = (cpp / 100) * points
        return {'points': points, 'cpp': cpp, 'total_usd': total_usd}
