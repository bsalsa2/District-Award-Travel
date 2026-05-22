import numpy as np
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

class LanguageModel:
    def __init__(self):
        self.model = AutoModelForSeq2SeqLM.from_pretrained('t5-base')
        self.tokenizer = AutoTokenizer.from_pretrained('t5-base')

    def generate_response(self, input_text):
        input_ids = self.tokenizer.encode(input_text, return_tensors='pt')
        output = self.model.generate(input_ids, max_length=100)
        response = self.tokenizer.decode(output[0], skip_special_tokens=True)
        return response

language_model = LanguageModel()
