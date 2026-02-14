from dataclasses import dataclass
from typing import List
from enum import Enum
import requests
import time


@dataclass
class VKUser:
    """
    Dataclass, представляющая пользователя VK.

    Attributes:
        id (int): Уникальный идентификатор пользователя в VK.
        first_name (str): Имя пользователя.
        last_name (str): Фамилия пользователя.
        profile_url (str): URL профиля пользователя в VK.
    """
    id: int
    first_name: str
    last_name: str
    profile_url: str


class VKSex(Enum):
    """
    Перечисление для указания пола при поиске пользователей.

    Значения соответствуют API VK:
        WOMEN = 1 — искать женщин.
        MEN = 2 — искать мужчин.
        ALL = 0 — искать всех.
    """
    WOMEN = 1
    MEN = 2
    ALL = 0


class VkClient:
    """
    Клиент для взаимодействия с API ВКонтакте.

    Предоставляет методы для поиска пользователей и получения фотографий.
    Автоматически добавляет токен доступа и версию API ко всем запросам.

    Attributes:
        token (str): Токен доступа к API VK.
        api_url (str): Базовый URL для вызова методов API.
    """
    def __init__(self, token: str):
        """
        Инициализирует клиент с токеном доступа.

        Args:
            token (str): Токен доступа к API VK.
        """
        self.token = token
        self.api_url = "https://api.vk.com/method/"

    def _get_common_params(self) -> dict:
        """
        Возвращает общие параметры, добавляемые ко всем запросам.

        Returns:
            dict: Словарь с параметрами 'access_token' и 'v' (версия API).
        """
        return {
            'access_token': self.token,
            'v': '5.199'
        }

    def search_users(self, city_id: int, age_from: int, age_to: int, sex: int) -> List[VKUser]:
    """
    Ищет пользователей ВКонтакте по заданным критериям.

    Args:
        city_id (int): ID города для поиска.
        age_from (int): Нижняя граница возраста.
        age_to (int): Верхняя граница возраста.
        sex (int): Пол пользователя (1 — женщины, 2 — мужчины, 0 — любые).

    Returns:
        List[VKUser]: Список найденных пользователей, у которых профиль открыт и есть фото.
        Возвращает пустой список при ошибках или отсутствии результатов.

    Example:
        >>> vk_client = VkClient(token)
        >>> users = vk_client.search_users(city_id=2, age_from=25, age_to=30, sex=VKSex.MEN)
        >>> for user in users:
        ...     print(user.first_name, user.last_name, user.profile_url)
    """
    params = {
        "city_id": city_id,
        "age_from": age_from,
        "age_to": age_to,
        "sex": sex.value if isinstance(sex, VKSex) else sex,
        "fields": "is_closed, has_photo"
    }
    data = self._request("users.search", params)

    if not data or 'response' not in data:
        print("Не удалось получить пользователей")
        return []

    users = []
    for item in data['response']['items']:
        if item['is_closed']:
            continue
        if not item['has_photo']:
            continue
        user_id = item['id']
        first_name = item['first_name']
        last_name = item['last_name']
        profile_url = f"https://vk.com/id{user_id}"
        users.append(VKUser(id=user_id, first_name=first_name, last_name=last_name,
                            profile_url=profile_url))
    return users

    def get_user_photos(self, user_id: int) -> List[str]:
        """
        Получает ID трёх самых популярных фотографий профиля пользователя.

        Выполняет паузу 0.2 секунды перед запросом для соблюдения лимитов API.

        Args:
            user_id (int): Уникальный идентификатор пользователя ВКонтакте.

        Returns:
            List[str]: Список строк в формате "photo<owner_id>_<photo_id>", пригодных
            для отправки через Bot API. Возвращает пустой список при ошибках.

        Example:
            >>> photos = vk_client.get_user_photos(12345)
            >>> print(photos)
            ['photo12345_45678', 'photo12345_45679', 'photo12345_45680']
        """
        time.sleep(0.2)
        params = {
            "owner_id": user_id,
            "album_id": "profile",
            "extended": 1,
            "photo_sizes": 1
        }
        photos = self._request("photos.get", params)

        if not photos or 'response' not in photos:
            print("Не удалось получить фото")
            return []

        photos_all = [
            {"likes": photo['likes']['count'],
             "id_photo": photo["id"],
             "owner_id": photo['owner_id'],
             }
            for photo in photos['response']['items']
        ]

        photos_all.sort(key=lambda photo: photo['likes'], reverse=True)
        pop_photo = photos_all[:3]
        attachments = [f"photo{photo['owner_id']}_{photo['id_photo']}" for photo in pop_photo]
        return attachments

    def _request(self, method_name: str, params: dict) -> dict:
        """
        Выполняет HTTP-запрос к VK API.

        Добавляет общие параметры (токен и версию API) и обрабатывает ошибки.

        Args:
            method_name (str): Название метода API (например, "users.search").
            params (dict): Параметры запроса.

        Returns:
            dict: Ответ API в формате JSON. При ошибках сети, парсинга или в случае ошибки
            от сервера ВКонтакте возвращается пустой словарь.
        """
        url = f"{self.api_url}{method_name}"
        all_params = {**self._get_common_params(), **params}
        try:
            response = requests.get(url, params=all_params, timeout=10)
            response.raise_for_status()
            data = response.json()
        except requests.RequestException as e:
            print(f"Ошибка сети: {e}")
            return {}
        except ValueError:
            print("Ошибка парсинга JSON")
            return {}

        if 'error' in data:
            error_msg = data['error'].get('error_msg', 'Unknown error')
            print(f"Ошибка API VK: {error_msg}")
            return {}

        return data
