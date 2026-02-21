from random import randrange
from dataclasses import dataclass
from typing import Dict, Optional, List, Tuple

import vk_api
from vk_api.longpoll import VkLongPoll, VkEventType
from vk_api.keyboard import VkKeyboard, VkKeyboardColor

from config import config
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

DEFAULT_CITY_ID = 1  # Москва
AGE_DELTA = 5        # ищем ±5 лет от возраста пользователя


@dataclass
class DialogState:
    city_id: int = DEFAULT_CITY_ID
    city_title: Optional[str] = None
    age: Optional[int] = None
    target_sex: VKSex = VKSex.ALL
    last_candidate_id: Optional[int] = None
    awaiting: Optional[str] = None  # "sex" | "age"


def build_keyboard() -> str:
    kb = VkKeyboard(one_time=False, inline=False)
    kb.add_button("Дальше", color=VkKeyboardColor.PRIMARY)
    kb.add_button("❤️ В избранное", color=VkKeyboardColor.POSITIVE)
    kb.add_line()
    kb.add_button("⛔️ В ЧС", color=VkKeyboardColor.NEGATIVE)
    kb.add_button("⭐️ Избранное", color=VkKeyboardColor.SECONDARY)
    kb.add_line()
    kb.add_button("🔄 Сменить настройки", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def build_sex_keyboard() -> str:
    kb = VkKeyboard(one_time=True, inline=False)
    kb.add_button("👩 Женщину", color=VkKeyboardColor.POSITIVE)
    kb.add_button("👨 Мужчину", color=VkKeyboardColor.PRIMARY)
    kb.add_line()
    kb.add_button("👥 Неважно", color=VkKeyboardColor.SECONDARY)
    return kb.get_keyboard()


def profile_url(vk_id: int) -> str:
    return f"https://vk.com/id{vk_id}"


class VkinderBot:
    def __init__(self):
        config.validate()

        self.vk_session = vk_api.VkApi(token=config.BOT_TOKEN)
        self.vk = self.vk_session.get_api()
        self.longpoll = VkLongPoll(self.vk_session)

        self.vk_user = VkClient(config.VK_TOKEN)

        self.db = DatabaseManager(config.POSTGRES_URI)

        self.kb_main = build_keyboard()
        self.kb_sex = build_sex_keyboard()
        self.state: Dict[int, DialogState] = {}

    def st(self, user_id: int) -> DialogState:
        if user_id not in self.state:
            self.state[user_id] = DialogState()
        return self.state[user_id]

    def write_msg(
        self,
        user_id: int,
        message: str,
        attachments: Optional[List[str]] = None,
        keyboard: Optional[str] = None,
    ):
        params = {
            "user_id": user_id,
            "message": message,
            "random_id": randrange(10**7),
            "keyboard": keyboard or self.kb_main,
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

    # ---------- DB ----------
    def upsert_user(self, user_id: int, first_name: str, last_name: str):
        s = self.db.get_session()
        try:
            UserRepository(s).create_or_update(
                user_id,
                first_name=first_name,
                last_name=last_name,
                has_photo=True,
            )
            self._commit(s)
        finally:
            s.close()

    def upsert_candidate(
        self,
        cand_id: int,
        first_name: str,
        last_name: str,
        sex: Optional[int],
        city: Optional[str],
        has_photo: bool = True,
    ):
        s = self.db.get_session()
        try:
            CandidateRepository(s).create_or_update(
                cand_id,
                first_name=first_name,
                last_name=last_name,
                sex=sex,
                city=city,
                has_photo=has_photo,
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
            SearchHistoryRepository(s).set_reaction(user_id, cand_id, "licked")
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

    # ---------- Settings flow ----------
    def start_settings_flow(self, user_id: int, prefix_text: Optional[str] = None):
        st = self.st(user_id)
        st.awaiting = "sex"
        msg = "Кого ищем?"
        if prefix_text:
            msg = prefix_text.strip() + "\n\n" + msg
        self.write_msg(user_id, msg, keyboard=self.kb_sex)

    def reset_settings(self, user_id: int):
        st = self.st(user_id)
        st.age = None
        st.target_sex = VKSex.ALL
        st.last_candidate_id = None
        st.awaiting = None

    # ---------- Dialog ----------
    def handle_start(self, user_id: int):
        st = self.st(user_id)
        st.last_candidate_id = None
        st.awaiting = None

        me = self.vk_user.get_user_profile(user_id)
        if not me:
            self.write_msg(user_id, "Не смог получить данные профиля. Проверь VK_TOKEN.")
            return

        self.upsert_user(user_id, me.first_name or "", me.last_name or "")

        st.city_id = getattr(me, "city_id", None) or DEFAULT_CITY_ID
        st.city_title = getattr(me, "city", None) or ("Москва" if st.city_id == 1 else None)

        city_line = f"Город поиска: {st.city_title or 'не указан'} "
        self.start_settings_flow(user_id, prefix_text=f"Старт ✅\n{city_line}")

    def handle_change_settings(self, user_id: int):
        self.reset_settings(user_id)
        self.start_settings_flow(user_id, prefix_text="Ок, давай поменяем настройки 🔄")

    def handle_sex(self, user_id: int, text: str):
        st = self.st(user_id)
        low = text.strip().lower()

        if "жен" in low:
            st.target_sex = VKSex.WOMEN
            who = "женщин"
        elif "муж" in low:
            st.target_sex = VKSex.MEN
            who = "мужчин"
        elif "неваж" in low:
            st.target_sex = VKSex.ALL
            who = "всех"
        else:
            self.write_msg(user_id, "Выбери вариант кнопкой 👇", keyboard=self.kb_sex)
            return

        st.awaiting = "age"
        self.write_msg(
            user_id,
            f"Ок, ищем: {who}.\n\n"
            f"Теперь напиши свой возраст числом (18–99).\n"
            f"Поиск будет по возрасту: (твой возраст − {AGE_DELTA}) … (твой возраст + {AGE_DELTA}).",
        )

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
        age_from = max(18, age - AGE_DELTA)
        age_to = min(99, age + AGE_DELTA)

        st.awaiting = None
        self.write_msg(
            user_id,
            f"Принято ✅\n"
            f"Буду искать кандидатов {age_from}–{age_to} лет.\n"
            f"Жми «Дальше» 👇",
        )

    def pick_next_candidate(self, user_id: int) -> Optional[Tuple[int, str, List[str]]]:
        st = self.st(user_id)
        if st.age is None:
            return None

        age_from = max(18, st.age - AGE_DELTA)
        age_to = min(99, st.age + AGE_DELTA)

        users = self.vk_user.search_users(
            city_id=st.city_id,
            age_from=age_from,
            age_to=age_to,
            sex=st.target_sex,
        )

        for cand in users:
            cid = cand.id
            if self.in_blacklist(user_id, cid):
                continue
            if self.was_shown(user_id, cid):
                continue

            self.upsert_candidate(
                cid,
                cand.first_name,
                cand.last_name,
                sex=cand.sex,
                city=cand.city,
                has_photo=True,
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

    def run(self):
        for event in self.longpoll.listen():
            if event.type != VkEventType.MESSAGE_NEW or not event.to_me:
                continue

            user_id = event.user_id
            text = (event.text or "").strip()
            low = text.lower()

            st = self.st(user_id)

            if st.awaiting == "sex":
                self.handle_sex(user_id, text)
                continue
            if st.awaiting == "age":
                self.handle_age(user_id, text)
                continue

            if low in ("/start", "start", "начать", "привет"):
                self.handle_start(user_id)
            elif low in ("🔄 сменить настройки", "сменить настройки", "настройки"):
                self.handle_change_settings(user_id)
            elif low in ("дальше", "next"):
                self.handle_next(user_id)
            elif low in ("❤️ в избранное", "в избранное"):
                self.handle_favorite(user_id)
            elif low in ("⛔️ в чс", "в чс", "чс"):
                self.handle_blacklist(user_id)
            elif low in ("⭐️ избранное", "избранное"):
                self.handle_list_favorites(user_id)
            else:
                self.write_msg(
                    user_id,
                    "Команды: /start, Дальше, ❤️ В избранное, ⛔️ В ЧС, ⭐️ Избранное, 🔄 Сменить настройки",
                )


if __name__ == "__main__":
    config.validate()
    create_database()
    DatabaseManager(config.POSTGRES_URI).create_tables()

    bot = VkinderBot()
    bot.run()