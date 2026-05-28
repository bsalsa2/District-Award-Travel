import numpy as np
from pydantic import BaseModel

class UserAuthenticator:
    def __init__(self):
        self.users = {}

    def add_user(self, username, password):
        self.users[username] = password

    def authenticate(self, username, password):
        if username in self.users and self.users[username] == password:
            return True
        else:
            return False

class User(BaseModel):
    id: int
    username: str
    password: str
