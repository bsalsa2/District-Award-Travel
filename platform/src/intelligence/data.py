import numpy as np
from transformers import AutoTokenizer
import torch

class AwardTravelData:
    def __init__(self, data_path):
        self.data_path = data_path
        self.tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')

    def load_data(self):
        data = []
        with open(self.data_path, 'r') as f:
            for line in f:
                input_text, label = line.strip().split('\t')
                inputs = self.tokenizer(input_text, return_tensors='pt')
                data.append({
                    'input_ids': inputs['input_ids'].flatten(),
                    'attention_mask': inputs['attention_mask'].flatten(),
                    'labels': torch.tensor(int(label))
                })
        return data

    def create_batches(self, data, batch_size=32):
        batches = []
        for i in range(0, len(data), batch_size):
            batch = {
                'input_ids': torch.stack([d['input_ids'] for d in data[i:i+batch_size]]),
                'attention_mask': torch.stack([d['attention_mask'] for d in data[i:i+batch_size]]),
                'labels': torch.stack([d['labels'] for d in data[i:i+batch_size]])
            }
            batches.append(batch)
        return batches
