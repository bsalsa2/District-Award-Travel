import sqlite3
import numpy as np

def get_user_profile():
    conn = sqlite3.connect('user_profiles.db')
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM user_profiles")
    profile = cursor.fetchone()
    conn.close()
    return profile

def update_user_profile(profile_data):
    conn = sqlite3.connect('user_profiles.db')
    cursor = conn.cursor()
    cursor.execute("UPDATE user_profiles SET name = ?, email = ?, phone = ? WHERE id = 1", (profile_data['name'], profile_data['email'], profile_data['phone']))
    conn.commit()
    conn.close()
    return "Profile updated successfully"
