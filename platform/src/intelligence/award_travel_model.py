import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from transformers import AutoModel, AutoTokenizer
from sklearn.metrics import accuracy_score

class AwardTravelModel(nn.Module):
    def __init__(self):
        super(AwardTravelModel, self).__init__()
        self.tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')
        self.model = AutoModel.from_pretrained('distilbert-base-uncased')
        self.dropout = nn.Dropout(0.1)
        self.classifier = nn.Linear(768, 8)

    def forward(self, input_ids, attention_mask):
        outputs = self.model(input_ids, attention_mask=attention_mask)
        pooled_output = outputs.pooler_output
        pooled_output = self.dropout(pooled_output)
        outputs = self.classifier(pooled_output)
        return outputs

class AwardTravelDataset(torch.utils.data.Dataset):
    def __init__(self, data, tokenizer):
        self.data = data
        self.tokenizer = tokenizer

    def __len__(self):
        return len(self.data)

    def __getitem__(self, idx):
        text = self.data.iloc[idx, 0]
        label = self.data.iloc[idx, 1]

        encoding = self.tokenizer.encode_plus(
            text,
            add_special_tokens=True,
            max_length=512,
            return_attention_mask=True,
            return_tensors='pt',
            padding='max_length',
            truncation=True
        )

        return {
            'input_ids': encoding['input_ids'].flatten(),
            'attention_mask': encoding['attention_mask'].flatten(),
            'label': torch.tensor(label, dtype=torch.long)
        }

def train_model(model, device, train_loader, optimizer, epoch):
    model.train()
    total_loss = 0
    for batch in train_loader:
        input_ids = batch['input_ids'].to(device)
        attention_mask = batch['attention_mask'].to(device)
        labels = batch['label'].to(device)

        optimizer.zero_grad()

        outputs = model(input_ids, attention_mask)
        loss = nn.CrossEntropyLoss()(outputs, labels)

        loss.backward()
        optimizer.step()

        total_loss += loss.item()

    print(f'Epoch {epoch+1}, Loss: {total_loss / len(train_loader)}')

def evaluate_model(model, device, test_loader):
    model.eval()
    total_correct = 0
    with torch.no_grad():
        for batch in test_loader:
            input_ids = batch['input_ids'].to(device)
            attention_mask = batch['attention_mask'].to(device)
            labels = batch['label'].to(device)

            outputs = model(input_ids, attention_mask)
            _, predicted = torch.max(outputs, dim=1)
            total_correct += (predicted == labels).sum().item()

    accuracy = total_correct / len(test_loader.dataset)
    return accuracy

# Example usage
if __name__ == '__main__':
    import pandas as pd

    # Load data
    data = pd.read_csv('data.csv')

    # Split data into training and testing sets
    from sklearn.model_selection import train_test_split
    train_data, test_data = train_test_split(data, test_size=0.2, random_state=42)

    # Create dataset and data loader
    dataset = AwardTravelDataset(train_data, AutoTokenizer.from_pretrained('distilbert-base-uncased'))
    batch_size = 32
    train_loader = torch.utils.data.DataLoader(dataset, batch_size=batch_size, shuffle=True)

    # Create model, device, and optimizer
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model = AwardTravelModel()
    model.to(device)
    optimizer = optim.Adam(model.parameters(), lr=1e-5)

    # Train model
    for epoch in range(5):
        train_model(model, device, train_loader, optimizer, epoch)

    # Evaluate model
    test_dataset = AwardTravelDataset(test_data, AutoTokenizer.from_pretrained('distilbert-base-uncased'))
    test_loader = torch.utils.data.DataLoader(test_dataset, batch_size=batch_size, shuffle=False)
    accuracy = evaluate_model(model, device, test_loader)
    print(f'Test Accuracy: {accuracy:.4f}')
