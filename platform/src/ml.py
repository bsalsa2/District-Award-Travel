import numpy as np
from sklearn.ensemble import RandomForestClassifier
from sklearn.feature_extraction.text import TfidfVectorizer

class ML:
    def __init__(self):
        self.vectorizer = TfidfVectorizer()
        self.classifier = RandomForestClassifier()
        
    def train(self, X, y):
        """
        Train the ML model.
        
        Args:
        X (list): The list of training examples.
        y (list): The list of training labels.
        """
        # Vectorize the training examples
        X_vectorized = self.vectorizer.fit_transform(X)
        
        # Train the classifier
        self.classifier.fit(X_vectorized, y)
        
    def rank_results(self, results):
        """
        Rank the search results using the ML model.
        
        Args:
        results (list): The list of search results.
        
        Returns:
        list: The ranked search results.
        """
        # Vectorize the search results
        results_vectorized = self.vectorizer.transform(results)
        
        # Predict the scores
        scores = self.classifier.predict_proba(results_vectorized)[:, 1]
        
        # Rank the results
        ranked_results = sorted(zip(results, scores), key=lambda x: x[1], reverse=True)
        
        # Return the ranked results
        return [result for result, score in ranked_results]
