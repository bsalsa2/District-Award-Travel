import numpy as np
from transformers import AutoModelForSequenceClassification, AutoTokenizer
import torch

class AwardTravelModel:
    def __init__(self, model_name):
        self.model = AutoModelForSequenceClassification.from_pretrained(model_name)
        self.tokenizer = AutoTokenizer.from_pretrained(model_name)

    def train(self, train_data, epochs=5):
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(device)
        optimizer = torch.optim.Adam(self.model.parameters(), lr=1e-5)

        for epoch in range(epochs):
            self.model.train()
            total_loss = 0
            for batch in train_data:
                input_ids = batch['input_ids'].to(device)
                attention_mask = batch['attention_mask'].to(device)
                labels = batch['labels'].to(device)

                optimizer.zero_grad()

                outputs = self.model(input_ids, attention_mask=attention_mask, labels=labels)
                loss = outputs.loss

                loss.backward()
                optimizer.step()

                total_loss += loss.item()
            print(f'Epoch {epoch+1}, Loss: {total_loss / len(train_data)}')

    def predict(self, input_text):
        device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(device)
        self.model.eval()

        inputs = self.tokenizer(input_text, return_tensors='pt')
        inputs = {k: v.to(device) for k, v in inputs.items()}

        with torch.no_grad():
            outputs = self.model(**inputs)
            logits = outputs.logits
            return torch.argmax(logits).item()
