from platform.src.intelligence.language_model import language_model

class ConversationalInterface:
    def __init__(self):
        self.language_model = language_model

    def process_input(self, input_text):
        response = self.language_model.generate_response(input_text)
        return response

conversational_interface = ConversationalInterface()
