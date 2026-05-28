import sqlite3

def create_database():
    # Connect to the database
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Create the payments table
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS payments (
            id INTEGER PRIMARY KEY,
            payment_id TEXT NOT NULL,
            status TEXT NOT NULL
        )
    """)
    conn.commit()
    conn.close()

def update_payment_status(payment_id, status):
    # Connect to the database
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Update the payment status
    cursor.execute("UPDATE payments SET status = ? WHERE payment_id = ?", (status, payment_id))
    conn.commit()
    conn.close()

def get_payment_status(payment_id):
    # Connect to the database
    conn = sqlite3.connect("database.db")
    cursor = conn.cursor()

    # Get the payment status
    cursor.execute("SELECT status FROM payments WHERE payment_id = ?", (payment_id,))
    status = cursor.fetchone()
    conn.close()

    return status[0] if status else None
