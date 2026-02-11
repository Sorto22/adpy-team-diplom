from dataclasses import dataclass
from typing import List, Optional
from enum import Enum
from config import Config
import requests

@dataclass
class VKUser:
    id: int
    first_name: str
    last_name: str
    profile_url: str
    # photos: List[str]

class VKSex(Enum):
    WOMEN = 1
    MEN = 2
    ALL = 0



class VkClient:
    def __init__(self, token: str):
        self.token = token

    def _get_comon_params(self):
        return {
            'access_token': self.token,
            'v': '5.199'
        }

    def search_users(self, city_id: int, age_from: int, age_to: int, sex: VKSex, offset: int = 0, count: int = 50) -> List[VKUser]:
        url = 'https://api.vk.com/method/users.search'
        params = {
            "city": city_id,
            "age_from": age_from,
            "age_to": age_to,
            "sex": sex.value,  # Enum -> число
            "count": count,
            "offset": offset,
            "has_photo": 1,
            "fields": "city,sex,is_closed,can_access_closed"
        }

        response = requests.get(url, params={**self._get_comon_params(), **params})
        data = response.json()
        users = []
        for item in data['response']['items']:
            user_id = item['id']
            first_name = item['first_name']
            last_name = item['last_name']
            profile_url = f"https://vk.com/id{user_id}"
            users.append(VKUser(id=user_id, first_name=first_name, last_name=last_name, profile_url=profile_url))
        return users

