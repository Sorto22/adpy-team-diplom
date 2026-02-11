import os
import random
import logging
from dataclasses import dataclass
from typing import Dict, Optional, Tuple, List

import vk_api
from vk_api.bot_longpoll import VkBotLongPoll, VkBotEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from config import Config
from core.init_db_for_vk_dating_bot import create_database
from core.models import DatabaseManager
from repo import Repo
from vkapi import VkClient, VKSex


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("vkinder")

COUNTRY_RU = 1


@dataclass
class DialogState:
    city_id: Optional[int] = None
    city_title: Optional[str] = None
    age: Optional[int] = None
    offset: int = 0
    last_candidate_id: Optional[int] = None
    awaiting: Optional[str] = None  # "city" | "age"


def profile_url(vk_id: int) -> str:
    return f"https://vk.com/id{vk_id}"


def keyboard_json() -> str:
    kb = VkKeyboard(one_time=False, inline=False)
    kb.add_button("Дальше", color=VkKeyboardColor.PRIMARY)
    kb.add_button("❤️ В избранное", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("⛔️ В ЧС", color=VkKeyboardColor.NEGATIVE)
    kb.add_button("⭐️ Избранное", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


class VkinderBot:
    def __init__(self):
        self.group_id = int(os.getenv("VK_GROUP_ID", "0"))
        if not self.group_id:
            raise RuntimeError("VK_GROUP_ID не задан в .env")

        if not Config.BOT_TOKEN or not Config.VK_TOKEN:
            raise RuntimeError("Проверь .env: BOT_TOKEN и VK_TOKEN должны быть заданы")

        self.kb = keyboard_json()
        self.vk_session = vk_api.VkApi(token=Config.BOT_TOKEN)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkBotLongPoll(self.vk_session, self.group_id)
        self.user_session = vk_api.VkApi(token=Config.VK_TOKEN)
        self.vk_user = self.user_session.get_api()
        self.vk_client = VkClient(Config.VK_TOKEN)
        self.db = DatabaseManager(Config.POSTGRES_URI)
        self.repo = Repo(self.db)

        self.state: Dict[int, DialogState] = {}

    def st(self, user_id: int) -> DialogState:
        if user_id not in self.state:
            self.state[user_id] = DialogState()
        return self.state[user_id]

    def send(self, user_id: int, text: str, attachments: Optional[List[str]] = None) -> None:
        payload = {
            "user_id": user_id,
            "random_id": random.randint(1, 2_147_483_647),
            "message": text,
            "keyboard": self.kb,
        }
        if attachments:
            payload["attachment"] = ",".join(attachments)

        self.vk.messages.send(**payload)

    def get_user_profile(self, user_id: int) -> dict:
        resp = self.vk_user.users.get(user_ids=user_id, fields="sex,bdate,city")
        return resp[0]

    def find_city(self, city_name: str) -> Tuple[Optional[int], Optional[str]]:
        resp = self.vk_user.database.getCities(country_id=COUNTRY_RU, q=city_name, count=10)
        items = resp.get("items", [])
        if not items:
            return None, None
        return int(items[0]["id"]), items[0].get("title")

    def top3_profile_photos_attachments(self, owner_id: int) -> List[str]:
        resp = self.vk_user.photos.get(owner_id=owner_id, album_id="profile", extended=1, count=50)
        items = resp.get("items", [])
        if not items:
            return []

        items_sorted = sorted(
            items,
            key=lambda p: int(p.get("likes", {}).get("count", 0)),
            reverse=True
        )[:3]

        atts = []
        for p in items_sorted:
            pid = p["id"]
            access_key = p.get("access_key")
            if access_key:
                atts.append(f"photo{owner_id}_{pid}_{access_key}")
            else:
                atts.append(f"photo{owner_id}_{pid}")
        return atts


    def handle_start(self, user_id: int) -> None:
        try:
            user = self.get_user_profile(user_id)
        except Exception as e:
            logger.exception("users.get failed: %s", e)
            self.send(user_id, "Не смог получить данные профиля. Проверь пользовательский токен VK_TOKEN.")
            return

        self.repo.upsert_user(user_id, user.get("first_name", ""), user.get("last_name", ""))

        st = self.st(user_id)

        city = user.get("city")
        if city and city.get("id"):
            st.city_id = int(city["id"])
            st.city_title = city.get("title")

        if not st.city_id:
            st.awaiting = "city"
            self.send(user_id, "Напиши город (например: Москва).")
            return

        st.awaiting = "age"
        self.send(user_id, "Напиши возраст числом (например: 25).")

    def handle_age(self, user_id: int, text: str) -> None:
        st = self.st(user_id)
        try:
            age = int(text.strip())
            if age < 18 or age > 99:
                raise ValueError
        except ValueError:
            self.send(user_id, "Возраст должен быть числом 18–99. Например: 25")
            return

        st.age = age
        st.awaiting = None
        self.send(user_id, "Ок. Жми «Дальше» 👇")

    def handle_city(self, user_id: int, text: str) -> None:
        st = self.st(user_id)
        city_id, title = self.find_city(text.strip())
        if not city_id:
            self.send(user_id, "Город не найден. Попробуй ещё раз (например: Москва).")
            return

        st.city_id = city_id
        st.city_title = title or text.strip()
        st.awaiting = "age"
        self.send(user_id, f"Ок, город: {st.city_title}. Теперь напиши возраст числом (например: 25).")

    def pick_next_candidate(self, user_id: int):
        st = self.st(user_id)
        if st.city_id is None or st.age is None:
            return None

        user = self.get_user_profile(user_id)
        user_sex = user.get("sex", 0)

        if user_sex == 1:
            search_sex_enum = VKSex.MEN
        elif user_sex == 2:
            search_sex_enum = VKSex.WOMEN
        else:
            search_sex_enum = VKSex.ALL

        age_from = max(18, st.age - 5)
        age_to = min(99, st.age + 5)

        for _ in range(10):
            try:
                users = self.vk_client.search_users(
                    city_id=st.city_id,
                    age_from=age_from,
                    age_to=age_to,
                    sex=search_sex_enum,
                    offset=st.offset,
                    count=50
                )
            except Exception as e:
                logger.exception("vkapi.search_users failed: %s", e)
                return None

            st.offset += 50

            for cand in users:
                cid = int(cand.id)

                # закрытых пропускаем
                if cand.is_closed and not cand.can_access_closed:
                    continue

                if self.repo.in_blacklist(user_id, cid):
                    continue

                if self.repo.was_shown(user_id, cid):
                    continue

                self.repo.upsert_candidate(
                    vk_id=cid,
                    first_name=cand.first_name,
                    last_name=cand.last_name,
                    sex=cand.sex,
                    city=cand.city_title,
                    has_photo=True
                )
                self.repo.mark_shown(user_id, cid)

                photos = self.top3_profile_photos_attachments(cid)
                return cand, photos

        return None

    def handle_next(self, user_id: int) -> None:
        try:
            found = self.pick_next_candidate(user_id)
        except Exception as e:
            logger.exception("pick_next_candidate failed: %s", e)
            self.send(user_id, "Ошибка поиска кандидатов. Проверь VK_TOKEN и доступ к API.")
            return

        if not found:
            self.send(user_id, "Кандидаты по текущим условиям закончились 😕")
            return

        cand, photos = found
        cid = int(cand.id)
        self.st(user_id).last_candidate_id = cid

        text = f"{cand.first_name} {cand.last_name}\n{profile_url(cid)}"
        self.send(user_id, text, attachments=photos)

    def handle_favorite(self, user_id: int) -> None:
        st = self.st(user_id)
        if not st.last_candidate_id:
            self.send(user_id, "Сначала нажми «Дальше».")
            return
        self.repo.add_favorite(user_id, st.last_candidate_id)
        self.send(user_id, "Добавил в избранное ⭐️")

    def handle_blacklist(self, user_id: int) -> None:
        st = self.st(user_id)
        if not st.last_candidate_id:
            self.send(user_id, "Сначала нажми «Дальше».")
            return
        self.repo.add_blacklist(user_id, st.last_candidate_id)
        self.send(user_id, "Добавил в чёрный список ⛔️")

    def handle_list_favorites(self, user_id: int) -> None:
        favs = self.repo.list_favorites(user_id)
        if not favs:
            self.send(user_id, "Избранное пустое.")
            return
        lines = ["⭐️ Избранное:"]
        for cid in favs[:50]:
            lines.append(profile_url(cid))
        self.send(user_id, "\n".join(lines))

    def run(self) -> None:
        logger.info("Bot started")
        for event in self.longpoll.listen():
            if event.type != VkBotEventType.MESSAGE_NEW:
                continue

            msg = event.obj.message
            user_id = msg["from_id"]
            text = (msg.get("text") or "").strip()

            st = self.st(user_id)

            if st.awaiting == "city":
                self.handle_city(user_id, text)
                continue
            if st.awaiting == "age":
                self.handle_age(user_id, text)
                continue

            low = text.lower()
            if low in ("/start", "start", "начать", "привет"):
                self.handle_start(user_id)
            elif low in ("дальше", "next"):
                self.handle_next(user_id)
            elif low in ("❤️ в избранное", "в избранное"):
                self.handle_favorite(user_id)
            elif low in ("⛔️ в чс", "в чс", "чс"):
                self.handle_blacklist(user_id)
            elif low in ("⭐️ избранное", "избранное"):
                self.handle_list_favorites(user_id)
            else:
                self.send(user_id, "Команды: /start, Дальше, ❤️ В избранное, ⛔️ В ЧС, ⭐️ Избранное")


if __name__ == "__main__":
    if not Config.POSTGRES_URI:
        raise RuntimeError("POSTGRES_URI не задан в .env")

    create_database()
    DatabaseManager(Config.POSTGRES_URI).create_tables()

    bot = VkinderBot()
    bot.run()

