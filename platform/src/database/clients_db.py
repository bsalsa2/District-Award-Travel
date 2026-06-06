import sqlite3
from typing import List, Dict

class ClientsDB:
    def __init__(self):
        self.conn = sqlite3.connect("clients.db")
        self.cursor = self.conn.cursor()
        self.create_table()

    def create_table(self):
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS clients (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                email TEXT NOT NULL,
                phone TEXT NOT NULL,
                created_at TEXT NOT NULL,
                total_miles_managed INTEGER NOT NULL,
                programs TEXT NOT NULL,
                notes TEXT NOT NULL,
                status TEXT NOT NULL
            )
        """)
        self.conn.commit()

    def create_client(self, client: Dict):
        self.cursor.execute("""
            INSERT INTO clients (name, email, phone, created_at, total_miles_managed, programs, notes, status)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            client.name,
            client.email,
            client.phone,
            client.created_at,
            client.total_miles_managed,
            str(client.programs),
            client.notes,
            client.status
        ))
        self.conn.commit()
        return self.cursor.lastrowid

    def get_all_clients(self):
        self.cursor.execute("SELECT * FROM clients")
        rows = self.cursor.fetchall()
        clients = []
        for row in rows:
            client = {
                "id": row[0],
                "name": row[1],
                "email": row[2],
                "phone": row[3],
                "created_at": row[4],
                "total_miles_managed": row[5],
                "programs": eval(row[6]),
                "notes": row[7],
                "status": row[8]
            }
            clients.append(client)
        return clients

    def get_client(self, id: int):
        self.cursor.execute("SELECT * FROM clients WHERE id = ?", (id,))
        row = self.cursor.fetchone()
        if row is None:
            return None
        client = {
            "id": row[0],
            "name": row[1],
            "email": row[2],
            "phone": row[3],
            "created_at": row[4],
            "total_miles_managed": row[5],
            "programs": eval(row[6]),
            "notes": row[7],
            "status": row[8]
        }
        return client

    def update_client(self, id: int, client: Dict):
        self.cursor.execute("""
            UPDATE clients
            SET name = ?, email = ?, phone = ?, created_at = ?, total_miles_managed = ?, programs = ?, notes = ?, status = ?
            WHERE id = ?
        """, (
            client.name,
            client.email,
            client.phone,
            client.created_at,
            client.total_miles_managed,
            str(client.programs),
            client.notes,
            client.status,
            id
        ))
        self.conn.commit()
