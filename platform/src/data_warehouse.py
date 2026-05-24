import pandas as pd
from platform.src.database import Database

class DataWarehouse:
    def __init__(self):
        self.database = Database()

    def get_award_travel_analytics(self):
        data = self.database.get_award_travel_data()
        df = pd.DataFrame([{"airline": d.airline, "route": d.route, "award_type": d.award_type, "miles_required": d.miles_required} for d in data])
        analytics = df.groupby(["airline", "route", "award_type"]).agg({"miles_required": "mean"}).reset_index()
        return analytics.to_dict(orient="records")

    def get_award_travel_insights(self):
        data = self.database.get_award_travel_data()
        df = pd.DataFrame([{"airline": d.airline, "route": d.route, "award_type": d.award_type, "miles_required": d.miles_required} for d in data])
        insights = df.groupby(["airline", "award_type"]).agg({"miles_required": "mean"}).reset_index()
        return insights.to_dict(orient="records")
