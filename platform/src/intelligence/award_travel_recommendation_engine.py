import numpy as np
from sklearn.ensemble import RandomForestRegressor
from sklearn.model_selection import train_test_split

class AwardTravelRecommendationEngine:
    def __init__(self):
        self.model = RandomForestRegressor()

    def get_recommendations(self, recommendation_request):
        # Load data
        data = np.load('data.npy')

        # Split data into training and testing sets
        X_train, X_test, y_train, y_test = train_test_split(data[:, :-1], data[:, -1], test_size=0.2, random_state=42)

        # Train model
        self.model.fit(X_train, y_train)

        # Make predictions
        predictions = self.model.predict(X_test)

        # Get recommendations
        recommendations = []
        for i, prediction in enumerate(predictions):
            recommendation = {
                'airline': 'Airline ' + str(i),
                'route': 'Route ' + str(i),
                'price': prediction
            }
            recommendations.append(recommendation)

        return recommendations
