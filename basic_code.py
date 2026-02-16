from random import randrange
from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from config import Config
from core.init_db_for_vk_dating_bot import create_database
from core.models import DatabaseManager

from core.base_repository import (
    UserRepository,
    CandidateRepository,
    FavoriteRepository,
    BlacklistRepository,
    SearchHistoryRepository,
)

from vkapi import VkClient, VKSex


COUNTRY_RU = 1


@dataclass
class DialogState:
    city_id: Optional[int] = None
    city_title: Optional[str] = None
    age: Optional[int] = None
    offset: int = 0
    last_candidate_id: Optional[int] = None
    awaiting: Optional[str] = None  # "city" | "age"


def build_keyboard() -> str:
    kb = VkKeyboard(one_time=False, inline=False)
    kb.add_button("Дальше", color=VkKeyboardColor.PRIMARY)
    kb.add_button("❤️ В избранное", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("⛔️ В ЧС", color=VkKeyboardColor.NEGATIVE)
    kb.add_button("⭐️ Избранное", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def profile_url(vk_id: int) -> str:
    return f"https://vk.com/id{vk_id}"


class VkinderBot:
    def __init__(self):
        Config.validate()

        self.vk_session = vk_api.VkApi(token=Config.BOT_TOKEN)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)

        self.vk_user = VkClient(Config.VK_TOKEN)

        self.db = DatabaseManager(Config.POSTGRES_URI)

        self.kb = build_keyboard()

        self.state: Dict[int, DialogState] = {}

    def st(self, user_id: int) -> DialogState:
        if user_id not in self.state:
            self.state[user_id] = DialogState()
        return self.state[user_id]

    def write_msg(self, user_id: int, message: str, attachments: Optional[List[str]] = None):
        params = {
            "user_id": user_id,
            "message": message,
            "random_id": randrange(10 ** 7),
            "keyboard": self.kb,
        }
        if attachments:
            params["attachment"] = ",".join(attachments)

        self.vk_session.method("messages.send", params)


    def _commit(self, session):
        try:
            session.commit()
        except Exception:
            session.rollback()
            raise

    def upsert_user(self, user_id: int, first_name: str, last_name: str):
        s = self.db.get_session()
        try:
            UserRepository(s).create_or_update(
                user_id,
                first_name=first_name,
                last_name=last_name,
                has_photo=True
            )
            self._commit(s)
        finally:
            s.close()

    def upsert_candidate(self, cand_id: int, first_name: str, last_name: str,
                         sex: Optional[int], city: Optional[str], has_photo: bool = True):
        s = self.db.get_session()
        try:
            CandidateRepository(s).create_or_update(
                cand_id,
                first_name=first_name,
                last_name=last_name,
                sex=sex,
                city=city,
                has_photo=has_photo
            )
            self._commit(s)
        finally:
            s.close()

    def mark_shown(self, user_id: int, cand_id: int):
        s = self.db.get_session()
        try:
            SearchHistoryRepository(s).add_view(user_id, cand_id)
            self._commit(s)
        finally:
            s.close()

    def was_shown(self, user_id: int, cand_id: int) -> bool:
        s = self.db.get_session()
        try:
            viewed = SearchHistoryRepository(s).get_viewed_candidates(user_id)
            return cand_id in viewed
        finally:
            s.close()

    def in_blacklist(self, user_id: int, cand_id: int) -> bool:
        s = self.db.get_session()
        try:
            return BlacklistRepository(s).is_blocked(user_id, cand_id)
        finally:
            s.close()

    def add_favorite(self, user_id: int, cand_id: int):
        s = self.db.get_session()
        try:
            FavoriteRepository(s).add_to_favorites(user_id, cand_id)
            SearchHistoryRepository(s).set_reaction(user_id, cand_id, "licked")  # у тебя так в constraint
            self._commit(s)
        finally:
            s.close()

    def add_blacklist(self, user_id: int, cand_id: int):
        s = self.db.get_session()
        try:
            BlacklistRepository(s).add_to_blacklist(user_id, cand_id)
            SearchHistoryRepository(s).set_reaction(user_id, cand_id, "blocked")
            self._commit(s)
        finally:
            s.close()

    def list_favorites(self, user_id: int) -> List[int]:
        s = self.db.get_session()
        try:
            fav_candidates = UserRepository(s).get_user_favorites(user_id)
            return [c.candidate_id for c in fav_candidates]
        finally:
            s.close()

    # ---------- Dialog logic ----------

    def handle_start(self, user_id: int):
        st = self.st(user_id)
        st.offset = 0
        st.last_candidate_id = None
        st.awaiting = None

        user = self.vk_user.get_user_profile(user_id)
        if not user:
            self.write_msg(user_id, "Не смог получить данные профиля. Проверь VK_TOKEN.")
            return

        self.upsert_user(user_id, user.get("first_name", ""), user.get("last_name", ""))

        city = user.get("city")
        if city and city.get("id"):
            st.city_id = int(city["id"])
            st.city_title = city.get("title")

        if not st.city_id:
            st.awaiting = "city"
            self.write_msg(user_id, "Напиши город (например: Москва).")
            return

        st.awaiting = "age"
        self.write_msg(user_id, "Напиши возраст числом (например: 25).")

    def handle_city(self, user_id: int, text: str):
        st = self.st(user_id)
        city_id, title = self.vk_user.find_city(text.strip(), country_id=COUNTRY_RU)
        if not city_id:
            self.write_msg(user_id, "Город не найден. Попробуй ещё раз (например: Санкт-Петербург).")
            return
        st.city_id = city_id
        st.city_title = title or text.strip()
        st.awaiting = "age"
        self.write_msg(user_id, f"Ок, город: {st.city_title}. Теперь напиши возраст (например: 25).")

    def handle_age(self, user_id: int, text: str):
        st = self.st(user_id)
        try:
            age = int(text.strip())
            if age < 18 or age > 99:
                raise ValueError
        except ValueError:
            self.write_msg(user_id, "Возраст должен быть числом 18–99. Например: 25")
            return
        st.age = age
        st.awaiting = None
        self.write_msg(user_id, "Ок. Жми «Дальше» 👇")

    def pick_next_candidate(self, user_id: int) -> Optional[Tuple[int, str, List[str]]]:
        st = self.st(user_id)
        if st.city_id is None or st.age is None:
            return None

        me = self.vk_user.get_user_profile(user_id)
        user_sex = int(me.get("sex") or 0)

        if user_sex == 1:
            search_sex = VKSex.MEN
        elif user_sex == 2:
            search_sex = VKSex.WOMEN
        else:
            search_sex = VKSex.ALL

        age_from = max(18, st.age - 5)
        age_to = min(99, st.age + 5)

        for _ in range(10):
            users = self.vk_user.search_users(
                city_id=st.city_id,
                age_from=age_from,
                age_to=age_to,
                sex=search_sex,
                offset=st.offset,
                count=50
            )
            st.offset += 50

            for cand in users:
                cid = cand.id

                if cand.is_closed and not cand.can_access_closed:
                    continue
                if self.in_blacklist(user_id, cid):
                    continue
                if self.was_shown(user_id, cid):
                    continue

                self.upsert_candidate(
                    cid,
                    cand.first_name,
                    cand.last_name,
                    sex=cand.sex,
                    city=cand.city_title,
                    has_photo=True
                )
                self.mark_shown(user_id, cid)

                photos = self.vk_user.get_user_photos(cid)
                text = f"{cand.first_name} {cand.last_name}\n{cand.profile_url}"
                return cid, text, photos

        return None

    def handle_next(self, user_id: int):
        found = self.pick_next_candidate(user_id)
        if not found:
            self.write_msg(user_id, "Кандидаты по текущим условиям закончились 😕")
            return

        cid, text, photos = found
        self.st(user_id).last_candidate_id = cid
        self.write_msg(user_id, text, attachments=photos)

    def handle_favorite(self, user_id: int):
        st = self.st(user_id)
        if not st.last_candidate_id:
            self.write_msg(user_id, "Сначала нажми «Дальше».")
            return
        self.add_favorite(user_id, st.last_candidate_id)
        self.write_msg(user_id, "Добавил в избранное ⭐️")

    def handle_blacklist(self, user_id: int):
        st = self.st(user_id)
        if not st.last_candidate_id:
            self.write_msg(user_id, "Сначала нажми «Дальше».")
            return
        self.add_blacklist(user_id, st.last_candidate_id)
        self.write_msg(user_id, "Добавил в чёрный список ⛔️")

    def handle_list_favorites(self, user_id: int):
        favs = self.list_favorites(user_id)
        if not favs:
            self.write_msg(user_id, "Избранное пустое.")
            return
        lines = ["⭐️ Избранное:"]
        for cid in favs[:50]:
            lines.append(profile_url(cid))
        self.write_msg(user_id, "\n".join(lines))

    # ---------- Main loop ----------

    def run(self):
        self.write_msg
        for event in self.longpoll.listen():
            if event.type != VkEventType.MESSAGE_NEW:
                continue
            if not event.to_me:
                continue

            user_id = event.user_id
            text = (event.text or "").strip()
            low = text.lower()

            st = self.st(user_id)

            if st.awaiting == "city":
                self.handle_city(user_id, text)
                continue
            if st.awaiting == "age":
                self.handle_age(user_id, text)
                continue

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
                self.write_msg(user_id, "Команды: /start, Дальше, ❤️ В избранное, ⛔️ В ЧС, ⭐️ Избранное")


if __name__ == "__main__":
    # Создание БД и таблиц
    Config.validate()
    create_database()
    DatabaseManager(Config.POSTGRES_URI).create_tables()

    bot = VkinderBot()
    bot.run()