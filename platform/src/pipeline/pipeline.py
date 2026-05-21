from platform.src.intelligence.award_prediction_model import AwardPredictionModel
from platform.src.pipeline.data_pipeline import DataPipeline

class Pipeline:
    def __init__(self, data_file):
        self.data_file = data_file
        self.data_pipeline = DataPipeline(data_file)
        self.model = AwardPredictionModel(100, 100, 100)

    def run(self):
        X_train, X_test, y_train, y_test = self.data_pipeline.get_data()
        self.model.train(X_train[:, 0], X_train[:, 1], X_train[:, 2], y_train)
        predictions = self.model.predict(X_test[:, 0], X_test[:, 1], X_test[:, 2])
        print('Accuracy:', accuracy_score(y_test, predictions))
