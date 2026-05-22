from platform.src.intelligence.model import AwardTravelModel
from platform.src.intelligence.data import AwardTravelData

def train_pipeline(data_path, model_name):
    data = AwardTravelData(data_path)
    train_data = data.load_data()
    batches = data.create_batches(train_data)

    model = AwardTravelModel(model_name)
    model.train(batches)

    return model
