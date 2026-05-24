from platform.src.pipeline.user_pipeline import UserPipeline
from platform.src.models.user import User

class UserIntelligence:
    def __init__(self, db_name: str):
        self.pipeline = UserPipeline(db_name)

    def create_user(self, user: User):
        self.pipeline.create_user(user)

    def get_user(self, user_id: int):
        return self.pipeline.get_user(user_id)

    def update_user(self, user: User):
        self.pipeline.update_user(user)

    def delete_user(self, user_id: int):
        self.pipeline.delete_user(user_id)
