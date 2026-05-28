import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import sqlite3
import pandas as pd

# Connect to the SQLite database
conn = sqlite3.connect('award_travel_database.db')
cursor = conn.cursor()

# Load the historical data
cursor.execute('SELECT * FROM award_travel_redemption_rates')
data = cursor.fetchall()

# Create a pandas DataFrame from the data
df = pd.DataFrame(data, columns=['id', 'award_type', 'travel_date', 'redemption_rate'])

# Convert the award type to a numerical value
df['award_type'] = df['award_type'].map({'economy': 0, 'premium_economy': 1, 'business': 2, 'first_class': 3})

# Convert the travel date to a numerical value
df['travel_date'] = pd.to_datetime(df['travel_date'])
df['travel_date'] = df['travel_date'].apply(lambda x: x.timestamp())

# Split the data into training and testing sets
X = df[['award_type', 'travel_date']]
y = df['redemption_rate']
X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)

# Train a random forest regressor model
model = RandomForestRegressor(n_estimators=100, random_state=42)
model.fit(X_train, y_train)

# Make predictions on the testing set
y_pred = model.predict(X_test)

# Evaluate the model
mse = mean_squared_error(y_test, y_pred)
print(f'Mean squared error: {mse}')

# Save the model to a file
import pickle
with open('award_travel_redemption_rate_model.pkl', 'wb') as f:
    pickle.dump(model, f)
