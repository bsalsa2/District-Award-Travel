import numpy as np
import pandas as pd
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import StandardScaler
from transformers import AutoTokenizer
from PIL import Image
import networkx as nx

def load_data():
    # Load text data
    text_data = pd.read_csv('text_data.csv')
    # Load image data
    image_data = []
    for file in os.listdir('image_data'):
        image_data.append(Image.open(os.path.join('image_data', file)))
    # Load graph data
    graph_data = []
    for file in os.listdir('graph_data'):
        graph_data.append(nx.read_graphml(os.path.join('graph_data', file)))
    # Load labels
    labels = pd.read_csv('labels.csv')
    return text_data, image_data, graph_data, labels

def preprocess_data(text_data, image_data, graph_data, labels):
    # Preprocess text data
    tokenizer = AutoTokenizer.from_pretrained('distilbert-base-uncased')
    text_data = text_data.apply(lambda x: tokenizer.encode(x, return_tensors='pt'))
    # Preprocess image data
    image_data = [transforms.ToTensor()(image) for image in image_data]
    # Preprocess graph data
    graph_data = [nx.to_numpy_array(graph) for graph in graph_data]
    # Preprocess labels
    labels = labels.apply(lambda x: torch.tensor(x))
    return text_data, image_data, graph_data, labels

def split_data(text_data, image_data, graph_data, labels):
    text_train, text_test, image_train, image_test, graph_train, graph_test, labels_train, labels_test = train_test_split(text_data, image_data, graph_data, labels, test_size=0.2, random_state=42)
    return text_train, text_test, image_train, image_test, graph_train, graph_test, labels_train, labels_test

def scale_data(text_train, text_test, image_train, image_test, graph_train, graph_test):
    scaler = StandardScaler()
    text_train = scaler.fit_transform(text_train)
    text_test = scaler.transform(text_test)
    image_train = scaler.fit_transform(image_train)
    image_test = scaler.transform(image_test)
    graph_train = scaler.fit_transform(graph_train)
    graph_test = scaler.transform(graph_test)
    return text_train, text_test, image_train, image_test, graph_train, graph_test

def create_dataset(text_train, text_test, image_train, image_test, graph_train, graph_test, labels_train, labels_test):
    train_dataset = MultimodalDataset(text_train, image_train, graph_train, labels_train)
    test_dataset = MultimodalDataset(text_test, image_test, graph_test, labels_test)
    return train_dataset, test_dataset

# Example usage
text_data, image_data, graph_data, labels = load_data()
text_data, image_data, graph_data, labels = preprocess_data(text_data, image_data, graph_data, labels)
text_train, text_test, image_train, image_test, graph_train, graph_test, labels_train, labels_test = split_data(text_data, image_data, graph_data, labels)
text_train, text_test, image_train, image_test, graph_train, graph_test = scale_data(text_train, text_test, image_train, image_test, graph_train, graph_test)
train_dataset, test_dataset = create_dataset(text_train, text_test, image_train, image_test, graph_train, graph_test, labels_train, labels_test)
