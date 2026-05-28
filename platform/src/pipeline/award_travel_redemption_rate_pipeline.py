import pandas as pd
import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error
import sqlite3
import pickle

# Load the historical data
def load_data():
    conn = sqlite3.connect('award_travel_database.db')
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM award_travel_redemption_rates')
    data = cursor.fetchall()
    df = pd.DataFrame(data, columns=['id', 'award_type', 'travel_date', 'redemption_rate'])
    return df

# Preprocess the data
def preprocess_data(df):
    df['award_type'] = df['award_type'].map({'economy': 0, 'premium_economy': 1, 'business': 2, 'first_class': 3})
    df['travel_date'] = pd.to_datetime(df['travel_date'])
    df['travel_date'] = df['travel_date'].apply(lambda x: x.timestamp())
    return df

# Train the model
def train_model(df):
    X = df[['award_type', 'travel_date']]
    y = df['redemption_rate']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor(n_estimators=100, random_state=42)
    model.fit(X_train, y_train)
    return model

# Evaluate the model
def evaluate_model(model, df):
    X = df[['award_type', 'travel_date']]
    y = df['redemption_rate']
    y_pred = model.predict(X)
    mse = mean_squared_error(y, y_pred)
    return mse

# Run the pipeline
def run_pipeline():
    df = load_data()
    df = preprocess_data(df)
    model = train_model(df)
    mse = evaluate_model(model, df)
    print(f'Mean squared error: {mse}')
    with open('award_travel_redemption_rate_model.pkl', 'wb') as f:
        pickle.dump(model, f)

run_pipeline()
