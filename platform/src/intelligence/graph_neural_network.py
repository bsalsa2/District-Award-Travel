import numpy as np
import torch
import torch.nn as nn
import torch.optim as optim
from torch_geometric.data import Data
from torch_geometric.nn import GCNConv
from torch_geometric.datasets import Planetoid

class GraphNeuralNetwork(nn.Module):
    def __init__(self):
        super(GraphNeuralNetwork, self).__init__()
        self.conv1 = GCNConv(1, 16)
        self.conv2 = GCNConv(16, 7)

    def forward(self, data):
        x, edge_index = data.x, data.edge_index

        x = torch.relu(self.conv1(x, edge_index))
        x = self.conv2(x, edge_index)
        return x

class AwardTravelRouteOptimizer:
    def __init__(self):
        self.model = GraphNeuralNetwork()
        self.device = torch.device('cuda' if torch.cuda.is_available() else 'cpu')
        self.model.to(self.device)

    def train(self, data):
        optimizer = optim.Adam(self.model.parameters(), lr=0.01)
        loss_fn = nn.CrossEntropyLoss()

        for epoch in range(100):
            optimizer.zero_grad()
            out = self.model(data)
            loss = loss_fn(out, data.y)
            loss.backward()
            optimizer.step()
            print(f'Epoch {epoch+1}, Loss: {loss.item()}')

    def predict(self, data):
        self.model.eval()
        with torch.no_grad():
            out = self.model(data)
            _, predicted = torch.max(out, 1)
            return predicted

# Example usage:
# data = Data(x=torch.randn(10, 1), edge_index=torch.tensor([[0, 1], [1, 0]], dtype=torch.long), y=torch.tensor([0, 1]))
# optimizer = AwardTravelRouteOptimizer()
# optimizer.train(data)
# prediction = optimizer.predict(data)
# print(prediction)
