import sqlite3
import pandas as pd

class DataPipeline:
    def __init__(self, db_path):
        self.db_path = db_path
        self.conn = sqlite3.connect(db_path)

    def load_data(self):
        # Load data from the database
        data = pd.read_sql_query("SELECT * FROM user_data", self.conn)

        return data

    def process_data(self, data):
        # Process the data by handling missing values and encoding categorical variables
        data.fillna(0, inplace=True)
        categorical_cols = data.select_dtypes(include=['object']).columns
        data[categorical_cols] = data[categorical_cols].apply(lambda x: pd.factorize(x)[0])

        return data

    def save_data(self, data):
        # Save the processed data to the database
        data.to_sql("processed_data", self.conn, if_exists="replace", index=False)
