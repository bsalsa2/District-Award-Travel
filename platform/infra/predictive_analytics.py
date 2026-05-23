import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_squared_error
import pickle
import os

# Load historical usage data
def load_data(file_path):
    data = pd.read_csv(file_path)
    return data

# Preprocess data
def preprocess_data(data):
    data['date'] = pd.to_datetime(data['date'])
    data['day_of_week'] = data['date'].dt.dayofweek
    data['month'] = data['date'].dt.month
    return data

# Train model
def train_model(data):
    X = data[['day_of_week', 'month']]
    y = data['usage']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestRegressor()
    model.fit(X_train, y_train)
    y_pred = model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    print(f'MSE: {mse}')
    return model

# Make predictions
def make_predictions(model, data):
    predictions = model.predict(data[['day_of_week', 'month']])
    return predictions

# Save model
def save_model(model, file_path):
    with open(file_path, 'wb') as f:
        pickle.dump(model, f)

# Load model
def load_model(file_path):
    with open(file_path, 'rb') as f:
        model = pickle.load(f)
    return model

# Main function
def main():
    data = load_data('platform/infra/historical_usage.csv')
    data = preprocess_data(data)
    model = train_model(data)
    save_model(model, 'platform/infra/model.pkl')
    predictions = make_predictions(model, data)
    print(predictions)

if __name__ == '__main__':
    main()
