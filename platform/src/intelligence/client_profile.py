import sqlite3
import json

class ClientProfile:
    def __init__(self, client_id: int):
        self.client_id = client_id
        self.conn = sqlite3.connect('client_profiles.db')
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute('''
            CREATE TABLE IF NOT EXISTS client_profiles
            (client_id INTEGER PRIMARY KEY, simulation_results TEXT)
        ''')
        self.conn.commit()

    def save_simulation_results(self, simulation_results: dict):
        self.cursor.execute('''
            INSERT OR REPLACE INTO client_profiles (client_id, simulation_results)
            VALUES (?, ?)
        ''', (self.client_id, json.dumps(simulation_results)))
        self.conn.commit()

    def get_simulation_results(self):
        self.cursor.execute('''
            SELECT simulation_results FROM client_profiles
            WHERE client_id = ?
        ''', (self.client_id,))
        simulation_results = self.cursor.fetchone()
        if simulation_results:
            return json.loads(simulation_results[0])
        else:
            return {}
