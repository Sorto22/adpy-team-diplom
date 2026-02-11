from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import date

from .models import User, Candidate
from .base_repository import UserRepository, CandidateRepository, FavoriteRepository


class UserCRUD:
    def __init__(self, session: Session):
        self.session = session
        self.user_repository = UserRepository(session)
        self.candidate_repository = CandidateRepository(session)
        self.favorite_repository = FavoriteRepository(session)

    def register_user(self, vk_id: int, first_name: str, last_name: str,
                       bdate: Optional[int] = None, city: Optional[str] = None,
                       sex: Optional[int] = None) -> User:

        user_data = {
            'first_name': first_name,
            'last_name': last_name,
            'bdate': bdate,
            'city': city,
            'sex': sex,
            'has_photo': True
        }
        return self.user_repository.create_or_update(vk_id, **user_data)

    def get_user(self, vk_id: int) -> Optional[User]:
        return self.user_repository.get_by_id(vk_id)

    def get_user_favorites(self, vk_id: int) -> List[Candidate]:
        return self.user_repository.get_user_favorites(vk_id)

    def get_favorites_count(self, vk_id: int) -> int:
        return len(self.user_repository.get_user_favorites(vk_id))
