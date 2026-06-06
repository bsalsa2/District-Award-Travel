import pandas as pd
from sklearn.preprocessing import StandardScaler
from platform.src.models.award_flight_forecaster import AwardFlightForecaster

class AwardFlightPipeline:
  def __init__(self):
    self.scaler = StandardScaler()
    self.forecaster = AwardFlightForecaster()

  def load_data(self):
    # Load historical award flight data
    data = pd.read_csv('award_flight_data.csv')
    return data

  def preprocess_data(self, data):
    # Preprocess the data (e.g., scale, encode categorical variables)
    X = data.drop('award_flight_availability', axis=1)
    y = data['award_flight_availability']
    X_scaled = self.scaler.fit_transform(X)
    return X_scaled, y

  def train_model(self, X, y):
    # Train the award flight forecaster model
    self.forecaster.train(X, y)

  def make_predictions(self, X):
    # Make predictions using the trained model
    predictions = self.forecaster.predict(X)
    return predictions

  def save_predictions(self, predictions):
    # Save the predictions to a file or database
    pd.DataFrame(predictions).to_csv('award_flight_predictions.csv', index=False)

# Example usage
if __name__ == '__main__':
  pipeline = AwardFlightPipeline()
  data = pipeline.load_data()
  X, y = pipeline.preprocess_data(data)
  pipeline.train_model(X, y)
  predictions = pipeline.make_predictions(X)
  pipeline.save_predictions(predictions)
