import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

# Load hotel price data from the database
import sqlite3
conn = sqlite3.connect('hotel_prices.db')
cursor = conn.cursor()
cursor.execute('SELECT price, timestamp FROM hotel_prices')
hotel_prices = cursor.fetchall()

# Convert data to NumPy arrays
X = np.array([price for price, _ in hotel_prices]).reshape(-1, 1)
y = np.array([timestamp for _, timestamp in hotel_prices])

# Split data into training and testing sets
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train a random forest regressor model
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Make predictions on the testing set
y_pred = model.predict(X_test)

# Evaluate the model
print(f'Model score: {model.score(X_test, y_test)}')
