import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split

class DataLoader:
    def __init__(self, file_path):
        self.file_path = file_path

    def load_data(self):
        data = pd.read_csv(self.file_path)
        return data

    def split_data(self, data):
        X = data.drop(['route_id'], axis=1)
        y = data['route_id']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        return X_train, X_test, y_train, y_test

# Example usage:
# data_loader = DataLoader('data/award_travel_routes.csv')
# data = data_loader.load_data()
# X_train, X_test, y_train, y_test = data_loader.split_data(data)
