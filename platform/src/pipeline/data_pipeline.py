import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

class DataPipeline:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data = self.load_data()

    def load_data(self):
        data = pd.read_csv(self.data_file)
        return data

    def preprocess_data(self):
        X = self.data.drop(['label'], axis=1)
        y = self.data['label']
        X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
        scaler = StandardScaler()
        X_train = scaler.fit_transform(X_train)
        X_test = scaler.transform(X_test)
        return X_train, X_test, y_train, y_test

    def get_data(self):
        return self.preprocess_data()
