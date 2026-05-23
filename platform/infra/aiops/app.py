import os
import requests
from flask import Flask, jsonify, request
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import train_test_split
import pandas as pd
import numpy as np
from sqlalchemy import create_engine

app = Flask(__name__)

# Load data from database
def load_data():
    url = 'postgresql://user:password@database:5432/database'
    engine = create_engine(url)
    df = pd.read_sql_table('data', engine)
    return df

# Train model
def train_model(df):
    X = df.drop(['target'], axis=1)
    y = df['target']
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    model = RandomForestClassifier()
    model.fit(X_train, y_train)
    return model

# Make predictions
def make_predictions(model, df):
    predictions = model.predict(df)
    return predictions

# Save predictions to database
def save_predictions(predictions):
    url = 'postgresql://user:password@database:5432/database'
    engine = create_engine(url)
    df = pd.DataFrame(predictions)
    df.to_sql('predictions', engine, if_exists='replace', index=False)

# API endpoint to get data
@app.route('/data', methods=['GET'])
def get_data():
    df = load_data()
    return jsonify(df.to_dict(orient='records'))

# API endpoint to send predictions
@app.route('/predictions', methods=['POST'])
def send_predictions():
    predictions = request.get_json()
    save_predictions(predictions)
    return jsonify({'message': 'Predictions saved successfully'})

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8081)
