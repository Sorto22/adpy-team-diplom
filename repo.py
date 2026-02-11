from typing import List, Optional
from sqlalchemy.orm import Session

from core.models import User, Candidate, Favorite, Blacklist, SearchHistory, DatabaseManager


class Repo:
    def __init__(self, db: DatabaseManager):
        self.db = db

    def get_session(self) -> Session:
        return self.db.get_session()


    @staticmethod
    def _normalize_candidate_sex(sex: Optional[int]) -> Optional[int]:
        # В БД допустимо: 0, 1, 2 или NULL (см. constraint)
        if sex in (0, 1, 2):
            return int(sex)
        return None

    def _set_reaction(self, s: Session, user_vk_id: int, candidate_id: int, reaction: str) -> None:
        rec = s.query(SearchHistory).filter(
            SearchHistory.user_vk_id == user_vk_id,
            SearchHistory.candidate_id == candidate_id
        ).first()
        if not rec:
            rec = SearchHistory(user_vk_id=user_vk_id, candidate_id=candidate_id)
            s.add(rec)
        rec.reaction = reaction

    # --- users ---

    def upsert_user(self, vk_id: int, first_name: str, last_name: str) -> None:
        with self.get_session() as s:
            u = s.get(User, vk_id)
            if u:
                u.first_name = first_name
                u.last_name = last_name
                s.commit()
                return

            s.add(User(
                vk_id=vk_id,
                first_name=first_name,
                last_name=last_name,
                has_photo=True
            ))
            s.commit()

    # --- candidates ---

    def upsert_candidate(
        self,
        vk_id: int,
        first_name: str,
        last_name: str,
        sex: Optional[int],
        city: Optional[str],
        has_photo: bool
    ) -> None:
        sex_db = self._normalize_candidate_sex(sex)

        with self.get_session() as s:
            c = s.get(Candidate, vk_id)
            if c:
                c.first_name = first_name
                c.last_name = last_name
                c.sex = sex_db
                c.city = city
                c.has_photo = has_photo
                s.commit()
                return

            s.add(Candidate(
                vk_id=vk_id,
                first_name=first_name,
                last_name=last_name,
                sex=sex_db,
                city=city,
                has_photo=has_photo
            ))
            s.commit()

    # --- search history ---

    def mark_shown(self, user_vk_id: int, candidate_id: int) -> None:
        with self.get_session() as s:
            exists = s.query(SearchHistory).filter(
                SearchHistory.user_vk_id == user_vk_id,
                SearchHistory.candidate_id == candidate_id
            ).first()
            if exists:
                return
            s.add(SearchHistory(user_vk_id=user_vk_id, candidate_id=candidate_id))
            s.commit()

    def was_shown(self, user_vk_id: int, candidate_id: int) -> bool:
        with self.get_session() as s:
            return s.query(SearchHistory).filter(
                SearchHistory.user_vk_id == user_vk_id,
                SearchHistory.candidate_id == candidate_id
            ).first() is not None

    # --- blacklist ---

    def add_blacklist(self, user_vk_id: int, candidate_id: int) -> None:
        with self.get_session() as s:
            exists = s.query(Blacklist).filter(
                Blacklist.user_vk_id == user_vk_id,
                Blacklist.candidate_id == candidate_id
            ).first()
            if exists:
                return

            s.add(Blacklist(user_vk_id=user_vk_id, candidate_id=candidate_id))
            self._set_reaction(s, user_vk_id, candidate_id, "blocked")
            s.commit()

    def in_blacklist(self, user_vk_id: int, candidate_id: int) -> bool:
        with self.get_session() as s:
            return s.query(Blacklist).filter(
                Blacklist.user_vk_id == user_vk_id,
                Blacklist.candidate_id == candidate_id
            ).first() is not None

    # --- favorites ---

    def add_favorite(self, user_vk_id: int, candidate_id: int) -> None:
        with self.get_session() as s:
            exists = s.query(Favorite).filter(
                Favorite.user_vk_id == user_vk_id,
                Favorite.candidate_id == candidate_id
            ).first()
            if exists:
                return

            s.add(Favorite(user_vk_id=user_vk_id, candidate_id=candidate_id))
            self._set_reaction(s, user_vk_id, candidate_id, "liked")
            s.commit()

    def list_favorites(self, user_vk_id: int) -> List[int]:
        with self.get_session() as s:
            rows = s.query(Favorite.candidate_id).filter(Favorite.user_vk_id == user_vk_id).all()
            return [int(r[0]) for r in rows]


