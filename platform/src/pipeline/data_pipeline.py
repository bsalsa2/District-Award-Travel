import pandas as pd
import numpy as np
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler

class DataPipeline:
    def __init__(self, data_path):
        self.data_path = data_path

    def load_data(self):
        data = pd.read_csv(self.data_path)
        return data

    def preprocess_data(self, data):
        # Preprocess data
        data = data.dropna()
        data = data.apply(lambda x: x.astype(str).str.lower())
        return data

    def split_data(self, data):
        # Split data into training and testing sets
        train_data, test_data = train_test_split(data, test_size=0.2, random_state=42)
        return train_data, test_data

    def scale_data(self, data):
        # Scale data
        scaler = StandardScaler()
        scaled_data = scaler.fit_transform(data)
        return scaled_data

    def run_pipeline(self):
        data = self.load_data()
        data = self.preprocess_data(data)
        train_data, test_data = self.split_data(data)
        scaled_train_data = self.scale_data(train_data)
        scaled_test_data = self.scale_data(test_data)
        return scaled_train_data, scaled_test_data

# Example usage
if __name__ == '__main__':
    pipeline = DataPipeline('data.csv')
    scaled_train_data, scaled_test_data = pipeline.run_pipeline()
    print(scaled_train_data.shape)
    print(scaled_test_data.shape)
