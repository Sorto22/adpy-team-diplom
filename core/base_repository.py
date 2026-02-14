from typing import Optional, TypeVar, Generic, List

from sqlalchemy import func, and_
from sqlalchemy.orm import Session
from datetime import datetime, date

from .models import User, Candidate, Blacklist, Favorite, SearchHistory, Base

ModelType = TypeVar("ModelType", bound=Base)


class BaseRepository(Generic[ModelType]):
    '''Базовый репозиторий с основными операциями'''
    def __init__(self, session: Session, model: type[ModelType]):
        self.session = session
        self.model = model

    def create(self, **kwargs):
        instance = self.model(**kwargs)
        self.session.add(instance)
        self.session.flush()
        return instance

    def get(self, id: int) -> Optional[ModelType]:
        return self.session.get(self.model, id)

    def get_all(self, skip: int = 0, limit: int = 100) -> list[ModelType]:
        return self.session.query(self.model).offset(skip).limit(limit).all()

    def update(self, id: int, **kwargs) -> Optional[ModelType]:
        instance = self.get(id)
        if instance:
            for key, value in kwargs.items():
                if hasattr(instance, key):
                    setattr(instance, key, value)
            self.session.flush()
        return instance

    def delete(self, id: int) -> Optional[ModelType]:
        instance = self.get(id)
        if instance:
            self.session.delete(instance)
            self.session.flush()
            return True
        return False

    def exists(self, **kwargs) -> bool:
        query = self.session.query(self.model)
        for key, value in kwargs.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.first() is not None

class UserRepository(BaseRepository[User]):
    '''репозиторий для работы с пользователями'''
    def __init__(self, session: Session):
        super().__init__(session, User)

    def get_by_vk_id(self, user_id: int) -> Optional[User]:
        return self.session.query(User).filter(User.user_id == user_id).first()

    def create_or_update(self, user_id: int, **user_data) -> User:
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
        '''получить всех избранных кандидатов'''
        favorites = self.session.query(Favorite).filter(Favorite.user_id == user_id).all()
        candidate_ids = [f.candidate_id for f in favorites]
        return self.session.query(Candidate).filter(Candidate.candidate_id.in_(candidate_ids)).all()

    def get_user_blacklist(self, user_id: int) -> list[Candidate]:
        blacklisted = self.session.query(Blacklist).filter(Blacklist.user_id == user_id).all()
        candidate_ids = [b.candidate_id for b in blacklisted]
        return self.session.query(Candidate).filter(Candidate.candidate_id.in_(candidate_ids)).all()

class CandidateRepository(BaseRepository[Candidate]):
    '''репозиторий для работы с кандидатими'''
    def __init__(self, session: Session):
        super().__init__(session, Candidate)

    def get_by_vk_id(self, candidate_id: int) -> Optional[Candidate]:
        return self.session.query(Candidate).filter(Candidate.candidate_id == candidate_id).first()


    def create_or_update(self, candidate_id: int, **candidate_data) -> Candidate:
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
                          exclude_ids: Optional[List[int]] = None, #мы же не показываем повторы?
                          limit: Optional[int] = 10 #достаточно?
                          ) -> list[Candidate]:
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
    '''репозиторий избранных'''
    def __init__(self, session: Session):
        super().__init__(session, Favorite)

    def get_by_user_and_candidate(self, user_id: int, candidate_id: int) -> Optional[Favorite]:
        '''получаем избранного по пользователю и кандидату'''
        return self.session.query(Favorite).filter(
            and_(
            Favorite.user_id == user_id,
            Favorite.candidate_id == candidate_id
            )
        ).first()

    def add_to_favorites(self, user_id: int, candidate_id: int) -> Favorite:
        if not self.exists(user_id=user_id, candidate_id=candidate_id):
            return self.create(user_id=user_id, candidate_id=candidate_id)
        return self.get_by_user_and_candidate(user_id=user_id, candidate_id=candidate_id)

    def remove_from_favorites(self, user_id: int, candidate_id: int) -> bool:
        favorite = self.get_by_user_and_candidate(user_id=user_id, candidate_id=candidate_id)
        if favorite:
            return self.delete(favorite.id)
        return False

    def get_favorite_candidate_ids(self, user_id: int) -> List[int]:
        favorites = self.session.query(Favorite).filter(
            Favorite.user_id == user_id
        ).all()
        favorited_candidates = [f.candidate_id for f in favorites]
        return favorited_candidates


class BlacklistRepository(BaseRepository[Blacklist]):
    def __init__(self, session: Session):
        super().__init__(session, Blacklist)

    def get_by_user_and_candidate(self, user_id: int, candidate_id: int) -> Optional[Blacklist]:
        return self.session.query(Blacklist).filter(
            and_(
                Blacklist.user_id == user_id,
                Blacklist.candidate_id == candidate_id
            )
        ).first()

    def add_to_blacklist(self, user_id: int, candidate_id: int) -> Blacklist:
        if not self.exists(user_id=user_id, candidate_id=candidate_id):
            return self.create(user_id=user_id, candidate_id=candidate_id)
        return self.get_by_user_and_candidate(user_id, candidate_id)

    def remove_from_blacklist(self, user_id: int, candidate_id: int) -> bool:
        blacklist = self.get_by_user_and_candidate(user_id, candidate_id)
        if blacklist:
            return self.delete(blacklist.id)
        return False

    def is_blocked(self, user_id: int, candidate_id: int) -> bool:
        '''проверка блокировки'''
        return self.exists(user_id=user_id, candidate_id=candidate_id)

    def get_blocked_candidates(self, user_id: int) -> List[int]:
        blacklist = self.session.query(Blacklist).filter(
            Blacklist.user_id == user_id
        ).all()
        blocked_candidates = [b.candidate_id for b in blacklist]
        return blocked_candidates

class SearchHistoryRepository(BaseRepository[SearchHistory]):
    def __init__(self, session: Session):
        super().__init__(session, SearchHistory)

    def get_by_user_and_candidate(self, user_id: int, candidate_id: int) -> Optional[SearchHistory]:
        return self.session.query(SearchHistory).filter(
            and_(
                SearchHistory.user_id == user_id,
                SearchHistory.candidate_id == candidate_id
            )
        ).first()

    def add_view(self, user_id: int, candidate_id: int) -> SearchHistory:
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
        history = self.get_by_user_and_candidate(user_id=user_id, candidate_id=candidate_id)
        if history:
            history.reaction = reaction
            self.session.flush()
        return history

    def get_viewed_candidates(self, user_id: int) -> List[int]:
        '''получить ids всех просмотренных кандидатов'''
        histories = self.session.query(SearchHistory).filter(
            SearchHistory.user_id == user_id
        ).all()
        viewed_candidates = [h.candidate_id for h in histories]
        return viewed_candidates

