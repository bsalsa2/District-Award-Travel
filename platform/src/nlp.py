import nltk
from nltk.tokenize import word_tokenize
from nltk.corpus import stopwords

class NLP:
    def __init__(self):
        nltk.download("punkt")
        nltk.download("stopwords")
        self.stop_words = set(stopwords.words("english"))
        
    def preprocess_query(self, query):
        """
        Preprocess a natural language query.
        
        Args:
        query (str): The natural language query.
        
        Returns:
        str: The preprocessed query.
        """
        # Tokenize the query
        tokens = word_tokenize(query)
        
        # Remove stop words
        tokens = [token for token in tokens if token.lower() not in self.stop_words]
        
        # Stem the tokens
        stemmed_tokens = [self.stem_token(token) for token in tokens]
        
        # Return the preprocessed query
        return " ".join(stemmed_tokens)
    
    def stem_token(self, token):
        """
        Stem a token.
        
        Args:
        token (str): The token to stem.
        
        Returns:
        str: The stemmed token.
        """
        # Use the Porter stemmer
        from nltk.stem import PorterStemmer
        stemmer = PorterStemmer()
        return stemmer.stem(token)
