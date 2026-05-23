import asyncio
import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords
from nltk.stem import WordNetLemmatizer

class NLP:
    def __init__(self):
        self.lemmatizer = WordNetLemmatizer()
        self.stop_words = set(stopwords.words("english"))

    async def process_query(self, query):
        # Tokenize the query
        tokens = word_tokenize(query)
        
        # Remove stop words and lemmatize the tokens
        processed_tokens = [self.lemmatizer.lemmatize(token) for token in tokens if token not in self.stop_words]
        
        # Extract the origin and destination from the query
        origin = None
        destination = None
        for token in processed_tokens:
            if token.lower() in ["from", "to"]:
                if origin is None:
                    origin = processed_tokens[processed_tokens.index(token) + 1]
                else:
                    destination = processed_tokens[processed_tokens.index(token) + 1]
        
        return {"origin": origin, "destination": destination}

    async def load_models(self):
        # Load the NLP models
        nltk.download("punkt")
        nltk.download("stopwords")
        nltk.download("wordnet")
