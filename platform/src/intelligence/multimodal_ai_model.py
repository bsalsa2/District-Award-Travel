import numpy as np
from transformers import AutoModelForSequenceClassification, AutoTokenizer
from PIL import Image
from torchvision import transforms
import torch
import torch.nn as nn
import torch.optim as optim
from torch.utils.data import Dataset, DataLoader
import networkx as nx
import matplotlib.pyplot as plt

class MultimodalDataset(Dataset):
    def __init__(self, text_data, image_data, graph_data, labels):
        self.text_data = text_data
        self.image_data = image_data
        self.graph_data = graph_data
        self.labels = labels

    def __len__(self):
        return len(self.text_data)

    def __getitem__(self, idx):
        text = self.text_data[idx]
        image = self.image_data[idx]
        graph = self.graph_data[idx]
        label = self.labels[idx]

        return {
            'text': text,
            'image': image,
            'graph': graph,
            'label': label
        }

class MultimodalModel(nn.Module):
    def __init__(self):
        super(MultimodalModel, self).__init__()
        self.text_model = AutoModelForSequenceClassification.from_pretrained('distilbert-base-uncased')
        self.image_model = nn.Sequential(
            nn.Conv2d(3, 6, kernel_size=3),
            nn.ReLU(),
            nn.MaxPool2d(2, 2),
            nn.Flatten(),
            nn.Linear(6 * 6 * 6, 128),
            nn.ReLU(),
            nn.Linear(128, 128)
        )
        self.graph_model = nn.Sequential(
            nn.Linear(128, 128),
            nn.ReLU(),
            nn.Linear(128, 128)
        )
        self.combination_model = nn.Sequential(
            nn.Linear(384, 128),
            nn.ReLU(),
            nn.Linear(128, 2)
        )

    def forward(self, text, image, graph):
        text_output = self.text_model(text)['logits']
        image_output = self.image_model(image)
        graph_output = self.graph_model(graph)
        combined_output = torch.cat((text_output, image_output, graph_output), dim=1)
        output = self.combination_model(combined_output)
        return output

def train_model(model, dataset, epochs=10):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    criterion = nn.CrossEntropyLoss()
    optimizer = optim.Adam(model.parameters(), lr=0.001)
    for epoch in range(epochs):
        model.train()
        total_loss = 0
        for batch in dataset:
            text = batch['text'].to(device)
            image = batch['image'].to(device)
            graph = batch['graph'].to(device)
            label = batch['label'].to(device)
            optimizer.zero_grad()
            output = model(text, image, graph)
            loss = criterion(output, label)
            loss.backward()
            optimizer.step()
            total_loss += loss.item()
        print(f'Epoch {epoch+1}, Loss: {total_loss / len(dataset)}')
    model.eval()

def evaluate_model(model, dataset):
    device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
    model.to(device)
    correct = 0
    with torch.no_grad():
        for batch in dataset:
            text = batch['text'].to(device)
            image = batch['image'].to(device)
            graph = batch['graph'].to(device)
            label = batch['label'].to(device)
            output = model(text, image, graph)
            _, predicted = torch.max(output, 1)
            correct += (predicted == label).sum().item()
    accuracy = correct / len(dataset)
    print(f'Accuracy: {accuracy:.4f}')

# Example usage
text_data = ['This is a sample text', 'This is another sample text']
image_data = [Image.open('image1.jpg'), Image.open('image2.jpg')]
graph_data = [nx.Graph(), nx.Graph()]
labels = [0, 1]
dataset = MultimodalDataset(text_data, image_data, graph_data, labels)
model = MultimodalModel()
train_model(model, dataset)
evaluate_model(model, dataset)
