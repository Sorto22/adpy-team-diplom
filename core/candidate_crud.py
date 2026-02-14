from typing import List, Optional
from sqlalchemy.orm import Session
from datetime import datetime, date

from .models import Candidate
from .base_repository import (CandidateRepository, SearchHistoryRepository,
                              BlacklistRepository, FavoriteRepository)


class CandidateCRUD:
    def __init__(self, session:Session):
        self.session = session
        self.candidate_repository = CandidateRepository(session)
        self.histories_repository = SearchHistoryRepository(session)
        self.blacklist_repository = BlacklistRepository(session)
        self.favorite_repository = FavoriteRepository(session)

    def get_candidate(self, candidate_id: int) -> Optional[Candidate]:
        return self.candidate_repository.get_by_vk_id(candidate_id)

    def save_new_candidate(self, vk_id: int, first_name: str, last_name: str,
                           bdate: Optional[date] = None, city: Optional[str] = None,
                           sex: Optional[int] = None, has_photo: bool = True) -> Candidate:
        user_data = {
            'first_name': first_name,
            'last_name': last_name,
            'bdate': bdate,
            'city': city,
            'sex': sex,
            'has_photo': has_photo
        }
        return self.candidate_repository.create_or_update(vk_id, **user_data)

    def find_candidates(self, user_vk_id: int, city: Optional[str] = None,
                            sex: Optional[int] = None, age_from: int = 18,
                            age_to: int = 99, limit: int = 10) -> List[Candidate]:
        viewed_ids = self.histories_repository.get_viewed_candidates(user_vk_id)
        blacklisted_ids = self.blacklist_repository.get_blocked_candidates(user_vk_id)
        favorite_ids = self.favorite_repository.get_favorite_candidate_ids(user_vk_id)

        excluded_ids = list(set(viewed_ids + blacklisted_ids + favorite_ids))

        candidates = self.candidate_repository.search_candidates(
            city=city,
            sex=sex,
            age_from=age_from,
            age_to=age_to,
            has_photo=True,
            exclude_ids=excluded_ids,
            limit=limit
        )
        return candidates

    def save_candidate_from_vk(self, vk_user_data: dict) -> Optional[Candidate]:
        """
        Сохранить кандидата из данных VK API.
        Удобный метод-обертка.
        """
        try:
            # Парсим данные из VK
            vk_id = vk_user_data['id']
            first_name = vk_user_data['first_name']
            last_name = vk_user_data['last_name']

            # Опциональные поля
            bdate = vk_user_data.get('bdate')
            if bdate and len(bdate.split('.')) == 3:
                # Конвертируем 'DD.MM.YYYY' в date
                day, month, year = map(int, bdate.split('.'))
                bdate = date(year, month, day)
            else:
                bdate = None

            city = vk_user_data.get('city', {}).get('title') if vk_user_data.get('city') else None
            sex = vk_user_data.get('sex')

            # Проверяем наличие фото
            has_photo = 'photo_max' in vk_user_data or 'photo_400' in vk_user_data

            return self.save_new_candidate(
                vk_id=vk_id,
                first_name=first_name,
                last_name=last_name,
                bdate=bdate,
                city=city,
                sex=sex,
                has_photo=has_photo
            )

        except Exception as e:
            print(f"❌ Ошибка при сохранении кандидата из VK: {e}")
            return None