import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split
from sklearn.metrics import mean_squared_error

class AwardFlightForecaster:
  def __init__(self):
    self.model = RandomForestRegressor()

  def train(self, X, y):
    X_train, X_test, y_train, y_test = train_test_split(X, y, test_size=0.2, random_state=42)
    self.model.fit(X_train, y_train)
    y_pred = self.model.predict(X_test)
    mse = mean_squared_error(y_test, y_pred)
    print(f'MSE: {mse}')

  def predict(self, X):
    return self.model.predict(X)

  def save(self):
    import pickle
    with open('award_flight_forecaster.pkl', 'wb') as f:
      pickle.dump(self.model, f)

  def load(self):
    import pickle
    with open('award_flight_forecaster.pkl', 'rb') as f:
      self.model = pickle.load(f)

# Example usage
if __name__ == '__main__':
  # Generate some sample data
  np.random.seed(42)
  X = np.random.rand(100, 10)
  y = np.random.rand(100)

  forecaster = AwardFlightForecaster()
  forecaster.train(X, y)
  forecaster.save()

  # Load the saved model and make predictions
  forecaster.load()
  predictions = forecaster.predict(X)
  print(predictions)
