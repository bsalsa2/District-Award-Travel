from platform.src.database import Database
from platform.src.models.user import User

class UserPipeline:
    def __init__(self, db_name: str):
        self.db = Database(db_name)

    def create_user(self, user: User):
        self.db.insert_user(user)

    def get_user(self, user_id: int):
        return self.db.get_user(user_id)

    def update_user(self, user: User):
        self.db.update_user(user)

    def delete_user(self, user_id: int):
        self.db.delete_user(user_id)
