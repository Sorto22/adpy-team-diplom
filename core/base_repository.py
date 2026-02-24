from typing import Optional, TypeVar, Generic, List

from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from datetime import datetime, date

from .models import User, Candidate, Blacklist, Favorite, SearchHistory, Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    """Базовый репозиторий с основными операциями CRUD.

    Предоставляет общие методы для работы с любым типом модели SQLAlchemy.
    """
    def __init__(self, session: Session, model: type[ModelType]):
        """Инициализирует репозиторий с сессией и моделью.

        Args:
            session: Активная сессия SQLAlchemy.
            model: Класс модели (например, User, Candidate).
        """
        self.session = session
        self.model = model

    def create(self, **kwargs) -> ModelType:
        """Создаёт и сохраняет новый экземпляр модели.

        Args:
            **kwargs: Поля и значения для создания объекта.

        Returns:
            Созданный и добавленный в сессию экземпляр модели.
        """
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.flush()
        return instance

    def get(self, id: int) -> Optional[ModelType]:
        """Получает экземпляр модели по его ID.

        Args:
            id: Первичный ключ объекта.

        Returns:
            Объект модели или None, если не найден.
        """
        return self.session.get(self.model, id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        """Получает список всех экземпляров модели с пагинацией.

        Args:
            skip: Количество пропускаемых записей (для пагинации).
            limit: Максимальное количество возвращаемых записей.

        Returns:
            Список объектов модели.
        """
        return self.session.query(self.model).offset(skip).limit(limit).all()

    def update(self, id: int, **kwargs) -> Optional[ModelType]:
        """Обновляет поля экземпляра модели по его ID.

        Args:
            id: Первичный ключ объекта.
            **kwargs: Поля и новые значения.

        Returns:
            Обновлённый объект модели или None, если не найден.
        """
        instance = self.get(id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            self.session.flush()
        return instance

    def delete(self, id: int) -> bool:
        """Удаляет экземпляр модели по его ID.

        Args:
            id: Первичный ключ объекта.

        Returns:
            True, если объект был найден и удалён, иначе False.
        """
        instance = self.get(id)
        if instance:
            self.session.delete(instance)
            self.session.flush()
            return True
        return False

    def exists(self, **kwargs) -> bool:
        """Проверяет существование экземпляра модели с заданными параметрами.

        Args:
            **kwargs: Поля и значения для поиска.

        Returns:
            True, если хотя бы один объект найден, иначе False.
        """
        query = self.session.query(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.first() is not None

class UserRepository(BaseRepository[User]):
    """Репозиторий для работы с пользователями.

    Расширяет базовый репозиторий, добавляя методы, специфичные для модели User.
    """
    def __init__(self, session: Session):
        """Инициализирует репозиторий пользователей.

        Args:
            session: Активная сессия SQLAlchemy.
        """
        super().__init__(session, User)

    def get_by_vk_id(self, user_id: int) -> Optional[User]:
        """Получает пользователя по его уникальному ID в ВКонтакте.

        Args:
            user_id: Уникальный идентификатор пользователя в ВК.

        Returns:
            Объект User или None, если не найден.
        """
        return self.session.query(User).filter(User.user_id == user_id).first()

    def create_or_update(self, user_id: int, **user_data) -> User:
        """Создаёт или обновляет пользователя по его VK ID.

        Если пользователь существует — обновляет поля, иначе создаёт нового.
        Сбрасывает updated_at при обновлении.

        Args:
            user_id: Уникальный идентификатор пользователя в ВК.
            **user_data: Поля для создания или обновления.

        Returns:
            Объект User (созданный или обновлённый).
        """
        user = self.get_by_vk_id(user_id)
        if user:
            for key, value in user_data.items():
                if hasattr(user, key) and value is not None:
                    setattr(user, key, value)
            user.updated_at = func.now()
        else:
            user = self.create(user_id=user_id, **user_data)
        self.session.flush()
        return user

    def get_user_favorites(self, user_id: int) -> list[Candidate]:
        """Получает всех кандидатов, добавленных пользователем в избранное.

        Выполняет JOIN через таблицу Favorite.

        Args:
            user_id: ID пользователя.

        Returns:
            Список объектов Candidate.
        """
        favorites = self.session.query(Favorite).filter(Favorite.user_id == user_id).all()
        candidate_ids = [f.candidate_id for f in favorites]
        return self.session.query(Candidate).filter(Candidate.candidate_id.in_(candidate_ids)).all()

    def get_user_blacklist(self, user_id: int) -> list[Candidate]:
        """Получает всех кандидатов, добавленных пользователем в чёрный список.

        Args:
            user_id: ID пользователя.

        Returns:
            Список объектов Candidate.
        """
        blacklisted = self.session.query(Blacklist).filter(Blacklist.user_id == user_id).all()
        candidate_ids = [b.candidate_id for b in blacklisted]
        return self.session.query(Candidate).filter(Candidate.candidate_id.in_(candidate_ids)).all()

class CandidateRepository(BaseRepository[Candidate]):
    """Репозиторий для работы с кандидатами.

    Расширяет базовый репозиторий, добавляя методы для поиска и управления кандидатами.
    """
    def __init__(self, session: Session):
        """Инициализирует репозиторий кандидатов.

        Args:
            session: Активная сессия SQLAlchemy.
        """
        super().__init__(session, Candidate)

    def get_by_vk_id(self, candidate_id: int) -> Optional[Candidate]:
        """Получает кандидата по его уникальному ID в ВКонтакте.

        Args:
            candidate_id: Уникальный идентификатор кандидата в ВК.

        Returns:
            Объект Candidate или None, если не найден.
        """
        return self.session.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()


    def create_or_update(self, candidate_id: int, **candidate_data) -> Candidate:
        """Создаёт или обновляет кандидата по его VK ID.

        Если кандидат существует — обновляет поля, иначе создаёт нового.
        Сбрасывает updated_at при обновлении.

        Args:
            candidate_id: Уникальный идентификатор кандидата в ВК.
            **candidate_data: Поля для создания или обновления.

        Returns:
            Объект Candidate (созданный или обновлённый).
        """
        candidate = self.get_by_vk_id(candidate_id)
        if candidate:
            for key, value in candidate_data.items():
                if hasattr(candidate, key) and value is not None:
                    setattr(candidate, key, value)
            candidate.updated_at = func.now()
        else:
            candidate = self.create(candidate_id=candidate_id, **candidate_data)
        self.session.flush()
        return candidate

    def search_candidates(self,
                          city: Optional[str] = None,
                          sex: Optional[int] = None,
                          age_from: Optional[int] = None,
                          age_to: Optional[int] = None,
                          has_photo: Optional[bool] = True,
                          exclude_ids: Optional[List[int]] = None,
                          limit: Optional[int] = 10
                          ) -> list[Candidate]:
        """Ищет кандидатов по заданным критериям.

        Поддерживает фильтрацию по городу, полу, возрасту, наличию фото
        и исключению уже показанных ID.

        Args:
            city: Название города (частичное совпадение).
            sex: Пол (0 — любой, 1 — женщина, 2 — мужчина).
            age_from: Минимальный возраст.
            age_to: Максимальный возраст.
            has_photo: Флаг наличия фотографии профиля.
            exclude_ids: Список ID кандидатов, которых нужно исключить.
            limit: Максимальное количество результатов.

        Returns:
            Список объектов Candidate, соответствующих критериям.
        """
        query = self.session.query(Candidate)

        if city:
            query = query.filter(Candidate.city.ilike(f'%{city}%'))
        if sex is not None:
            query = query.filter(Candidate.sex == sex)
        if age_from is not None or age_to is not None:
            today = date.today()
            if age_from is not None:
                max_birth_date = date(today.year - age_from, today.month, today.day)
                query = query.filter(Candidate.bdate <= max_birth_date)
            if age_to is not None:
                min_birth_date = date(today.year - age_to - 1, today.month, today.day)
                query = query.filter(Candidate.bdate >= min_birth_date)
        if has_photo:
            query = query.filter(Candidate.has_photo == True)
        if exclude_ids:
            query = query.filter(Candidate.candidate_id.notin_(exclude_ids))

        return query.limit(limit).all()


class FavoriteRepository(BaseRepository[Favorite]):
    """Репозиторий для работы с избранными кандидатами.

    Управляет связями "пользователь — избранный кандидат".
    """
    def __init__(self, session: Session):
        """Инициализирует репозиторий избранных.

        Args:
            session: Активная сессия SQLAlchemy.
        """
        super().__init__(session, Favorite)

    def get_by_user_and_candidate(self, user_id: int, candidate_id: int) -> Optional[Favorite]:
        """Получает запись избранного по ID пользователя и кандидата.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            Объект Favorite или None, если связь не найдена.
        """
        return self.session.query(Favorite).filter(
            and_(
            Favorite.user_id == user_id,
            Favorite.candidate_id == candidate_id
            )
        ).first()

    def add_to_favorites(self, user_id: int, candidate_id: int) -> Favorite:
        """Добавляет кандидата в избранное пользователя.

        Если связь уже существует — возвращает существующую запись.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            Объект Favorite (созданный или существующий).
        """
        if not self.exists(user_id=user_id, candidate_id=candidate_id):
            return self.create(user_id=user_id, candidate_id=candidate_id)
        return self.get_by_user_and_candidate(user_id=user_id, candidate_id=candidate_id)

    def remove_from_favorites(self, user_id: int, candidate_id: int) -> bool:
        """Удаляет кандидата из избранного пользователя.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            True, если запись была найдена и удалена, иначе False.
        """
        favorite = self.get_by_user_and_candidate(user_id=user_id, candidate_id=candidate_id)
        if favorite:
            return self.delete(favorite.id)
        return False

    def get_favorite_candidate_ids(self, user_id: int) -> List[int]:
        """Получает список ID кандидатов, находящихся в избранном у пользователя.

        Args:
            user_id: ID пользователя.

        Returns:
            Список ID кандидатов.
        """
        favorites = self.session.query(Favorite).filter(
            Favorite.user_id == user_id
        ).all()
        favorited_candidates = [f.candidate_id for f in favorites]
        return favorited_candidates


class BlacklistRepository(BaseRepository[Blacklist]):
    """Репозиторий для работы с чёрным списком пользователей.

    Управляет блокировками кандидатов.
    """
    def __init__(self, session: Session):
        """Инициализирует репозиторий чёрного списка.

        Args:
            session: Активная сессия SQLAlchemy.
        """
        super().__init__(session, Blacklist)

    def get_by_user_and_candidate(self, user_id: int, candidate_id: int) -> Optional[Blacklist]:
        """Получает запись блокировки по ID пользователя и кандидата.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            Объект Blacklist или None, если не найден.
        """
        return self.session.query(Blacklist).filter(
            and_(
                Blacklist.user_id == user_id,
                Blacklist.candidate_id == candidate_id
            )
        ).first()

    def add_to_blacklist(self, user_id: int, candidate_id: int) -> Blacklist:
        """Добавляет кандидата в чёрный список пользователя.

        Если запись уже существует — возвращает её.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            Объект Blacklist (созданный или существующий).
        """
        if not self.exists(user_id=user_id, candidate_id=candidate_id):
            return self.create(user_id=user_id, candidate_id=candidate_id)
        return self.get_by_user_and_candidate(user_id, candidate_id)

    def remove_from_blacklist(self, user_id: int, candidate_id: int) -> bool:
        """Удаляет кандидата из чёрного списка пользователя.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            True, если запись была удалена, иначе False.
        """
        blacklist = self.get_by_user_and_candidate(user_id, candidate_id)
        if blacklist:
            return self.delete(blacklist.id)
        return False

    def is_blocked(self, user_id: int, candidate_id: int) -> bool:
        """Проверяет, находится ли кандидат в чёрном списке пользователя.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            True, если кандидат заблокирован, иначе False.
        """
        return self.exists(user_id=user_id, candidate_id=candidate_id)

    def get_blocked_candidates(self, user_id: int) -> List[int]:
        """Получает список ID кандидатов, находящихся в чёрном списке у пользователя.

        Args:
            user_id: ID пользователя.

        Returns:
            Список ID заблокированных кандидатов.
        """
        blacklist = self.session.query(Blacklist).filter(
            Blacklist.user_id == user_id
        ).all()
        blocked_candidates = [b.candidate_id for b in blacklist]
        return blocked_candidates

class SearchHistoryRepository(BaseRepository[SearchHistory]):
    """Репозиторий для работы с историей просмотров кандидатов.

    Отслеживает, какие кандидаты были показаны пользователю и какую реакцию он оставил.
    """
    def __init__(self, session: Session):
        """Инициализирует репозиторий истории просмотров.

        Args:
            session: Активная сессия SQLAlchemy.
        """
        super().__init__(session, SearchHistory)

    def get_by_user_and_candidate(self, user_id: int, candidate_id: int) -> Optional[SearchHistory]:
        """Получает запись истории просмотра по ID пользователя и кандидата.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            Объект SearchHistory или None, если запись не найдена.
        """
        return self.session.query(SearchHistory).filter(
            and_(
                SearchHistory.user_id == user_id,
                SearchHistory.candidate_id == candidate_id
            )
        ).first()

    def add_view(self, user_id: int, candidate_id: int) -> SearchHistory:
        """Отмечает, что кандидат был показан пользователю.

        Если запись уже существует — обновляет время показа, иначе создаёт новую.

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.

        Returns:
            Объект SearchHistory (созданный или обновлённый).
        """
        history = self.get_by_user_and_candidate(user_id=user_id, candidate_id=candidate_id)
        if history:
            history.shown_at = func.now()
        else:
            history = self.create(
                user_id=user_id,
                candidate_id=candidate_id
            )
        self.session.flush()
        return history

    def set_reaction(self, user_id: int, candidate_id: int, reaction: str) -> Optional[SearchHistory]:
        """Устанавливает реакцию пользователя на кандидата (например, "licked" или "blocked").

        Args:
            user_id: ID пользователя.
            candidate_id: ID кандидата.
            reaction: Тип реакции (например, 'licked', 'blocked').

        Returns:
            Объект SearchHistory с обновлённой реакцией или None, если запись не найдена.
        """
        history = self.get_by_user_and_candidate(user_id=user_id, candidate_id=candidate_id)
        if history:
            history.reaction = reaction
            self.session.flush()
        return history

    def get_viewed_candidates(self, user_id: int) -> List[int]:
        """Получает список ID всех кандидатов, показанных пользователю.

        Args:
            user_id: ID пользователя.

        Returns:
            Список ID кандидатов, которые были показаны.
        """
        histories = self.session.query(SearchHistory).filter(
            SearchHistory.user_id == user_id
        ).all()
        viewed_candidates = [h.candidate_id for h in histories]
        return viewed_candidates

