import sqlite3

def create_database(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS search_results (
            id INTEGER PRIMARY KEY,
            route TEXT,
            date TEXT,
            awards TEXT
        )
    """)
    conn.commit()
    conn.close()

if __name__ == "__main__":
    create_database("search_results.db")
