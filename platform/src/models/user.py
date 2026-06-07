class User:
    def __init__(self, id, username, password):
        self.id = id
        self.username = username
        self.password = password

def authenticate_user(username, password):
    # Authenticate the user
    users = [
        User(1, "jeff", "password123"),
        User(2, "john", "password456")
    ]
    for user in users:
        if user.username == username and user.password == password:
            return user
    return None

def verify_token(token):
    # Verify the token
    # For simplicity, assume the token is the user ID
    users = [
        User(1, "jeff", "password123"),
        User(2, "john", "password456")
    ]
    for user in users:
        if user.id == int(token):
            return user
    return None

def generate_token(user):
    # Generate a token
    # For simplicity, assume the token is the user ID
    return str(user.id)
