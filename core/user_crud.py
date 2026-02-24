from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import date

from .models import User, Candidate
from .base_repository import UserRepository, CandidateRepository, FavoriteRepository


class UserCRUD:
    """Класс для бизнес-логики, связанной с пользователями.

    Агрегирует репозитории и предоставляет удобные методы для работы с пользователями.
    """
    def __init__(self, session: Session):
        """Инициализирует CRUD операции для пользователей.

        Args:
            session: Активная сессия SQLAlchemy.
        """
        self.session = session
        self.user_repository = UserRepository(session)
        self.candidate_repository = CandidateRepository(session)
        self.favorite_repository = FavoriteRepository(session)

    def register_user(self, vk_id: int, first_name: str, last_name: str,
                       bdate: Optional[int] = None, city: Optional[str] = None,
                       sex: Optional[int] = None) -> User:
        """Регистрирует или обновляет пользователя в системе.

        Args:
            vk_id: Уникальный идентификатор пользователя в ВК.
            first_name: Имя.
            last_name: Фамилия.
            bdate: Дата рождения.
            city: Город.
            sex: Пол.

        Returns:
            Объект User.
        """

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
        """Получает пользователя по его VK ID.

        Args:
            vk_id: Уникальный идентификатор пользователя в ВК.

        Returns:
            Объект User или None, если не найден.
        """
        return self.user_repository.get_by_vk_id(vk_id)

    def get_user_favorites(self, vk_id: int) -> List[Candidate]:
        """Получает список избранных кандидатов пользователя.

        Args:
            vk_id: ID пользователя.

        Returns:
            Список объектов Candidate.
        """
        return self.user_repository.get_user_favorites(vk_id)

    def get_favorites_count(self, vk_id: int) -> int:
        """Возвращает количество кандидатов в избранном у пользователя.

        Args:
            vk_id: ID пользователя.

        Returns:
            Количество избранных кандидатов.
        """
        return len(self.user_repository.get_user_favorites(vk_id))
