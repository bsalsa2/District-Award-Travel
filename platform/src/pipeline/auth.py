from fastapi import Depends, FastAPI, HTTPException
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel
from sqlite3 import Error
import sqlite3
import numpy as np

# Define the database connection
def create_connection():
    conn = None
    try:
        conn = sqlite3.connect('database.db')
        return conn
    except Error as e:
        print(e)

# Create a table for users
def create_table(conn):
    sql = """ CREATE TABLE IF NOT EXISTS users (
                                        id integer PRIMARY KEY,
                                        username text NOT NULL,
                                        password text NOT NULL
                                    ); """
    try:
        c = conn.cursor()
        c.execute(sql)
    except Error as e:
        print(e)

# Insert a new user into the table
def insert_user(conn, user):
    sql = ''' INSERT INTO users(username, password)
              VALUES(?,?) '''
    try:
        c = conn.cursor()
        c.execute(sql, user)
        conn.commit()
        return c.lastrowid
    except Error as e:
        print(e)

# Authenticate a user
def authenticate_user(conn, username, password):
    sql = ''' SELECT * FROM users
              WHERE username = ? AND password = ? '''
    try:
        c = conn.cursor()
        c.execute(sql, (username, password))
        return c.fetchone()
    except Error as e:
        print(e)

# Initialize the database connection
conn = create_connection()
create_table(conn)
