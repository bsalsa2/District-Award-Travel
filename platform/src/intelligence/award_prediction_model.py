import numpy as np
from tensorflow.keras.models import Model
from tensorflow.keras.layers import Input, Dense, Embedding, concatenate
from tensorflow.keras.preprocessing.text import Tokenizer
from tensorflow.keras.preprocessing.sequence import pad_sequences
from tensorflow.keras.utils import to_categorical
from sklearn.model_selection import train_test_split
from sklearn.metrics import accuracy_score, classification_report, confusion_matrix

class AwardPredictionModel:
    def __init__(self, num_users, num_awards, num_behaviors):
        self.num_users = num_users
        self.num_awards = num_awards
        self.num_behaviors = num_behaviors
        self.model = self.build_model()

    def build_model(self):
        user_input = Input(shape=(1,), name='user_input')
        award_input = Input(shape=(1,), name='award_input')
        behavior_input = Input(shape=(1,), name='behavior_input')

        user_embedding = Embedding(self.num_users, 10, input_length=1)(user_input)
        award_embedding = Embedding(self.num_awards, 10, input_length=1)(award_input)
        behavior_embedding = Embedding(self.num_behaviors, 10, input_length=1)(behavior_input)

        x = concatenate([user_embedding, award_embedding, behavior_embedding])
        x = Dense(64, activation='relu')(x)
        x = Dense(32, activation='relu')(x)
        x = Dense(3, activation='softmax')(x)

        model = Model(inputs=[user_input, award_input, behavior_input], outputs=x)
        model.compile(loss='categorical_crossentropy', optimizer='adam', metrics=['accuracy'])
        return model

    def train(self, user_data, award_data, behavior_data, labels):
        user_sequences = pad_sequences(user_data, maxlen=1)
        award_sequences = pad_sequences(award_data, maxlen=1)
        behavior_sequences = pad_sequences(behavior_data, maxlen=1)
        labels = to_categorical(labels)

        X_train, X_test, y_train, y_test = train_test_split([user_sequences, award_sequences, behavior_sequences], labels, test_size=0.2, random_state=42)

        self.model.fit(X_train, y_train, epochs=10, batch_size=32, validation_data=(X_test, y_test))

    def predict(self, user_data, award_data, behavior_data):
        user_sequences = pad_sequences(user_data, maxlen=1)
        award_sequences = pad_sequences(award_data, maxlen=1)
        behavior_sequences = pad_sequences(behavior_data, maxlen=1)

        predictions = self.model.predict([user_sequences, award_sequences, behavior_sequences])
        return np.argmax(predictions, axis=1)
