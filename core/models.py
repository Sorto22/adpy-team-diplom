from typing import Optional
from sqlalchemy import (
    Boolean, Column, Date, DateTime, ForeignKey, Integer, String,
    CheckConstraint, UniqueConstraint, Index, func, create_engine
)

from sqlalchemy.orm import declarative_base, relationship, sessionmaker, Session

from config import Config

Base = declarative_base()


class User(Base):
    """Модель пользователя.

    Хранит основные данные о пользователе бота, включая профиль и настройки.
    """
    __tablename__ = 'users'

    user_id = Column(Integer, primary_key=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    bdate = Column(Date, nullable=True)
    city = Column(String(50), nullable=True)
    has_photo = Column(Boolean, nullable=False)
    sex = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    # Связи
    blacklisted = relationship("Blacklist",
                               back_populates="user",
                               cascade="all, delete-orphan")
    favorites = relationship("Favorite",
                             back_populates="user",
                             cascade="all, delete-orphan")
    search_history = relationship("SearchHistory",
                                  back_populates="user",
                                  cascade="all, delete-orphan")

    __table_args__ = (
        CheckConstraint('sex IN (0, 1, 2)', name='check_user_sex'),
    )

    def __repr__(self):
        return f"<User(user_id={self.user_id}, first_name={self.first_name}, last_name={self.last_name})>"


class Candidate(Base):
    """Модель кандидата для знакомства.

    Хранит данные о пользователях, найденных для показа.
    """
    __tablename__ = 'candidates'
    candidate_id = Column(Integer, primary_key=True)
    first_name = Column(String(50), nullable=False)
    last_name = Column(String(50), nullable=False)
    bdate = Column(Date, nullable=True)
    city = Column(String(50), nullable=True)
    has_photo = Column(Boolean, nullable=False)
    sex = Column(Integer, nullable=True)
    updated_at = Column(DateTime(timezone=True),
                        server_default=func.now(),
                        nullable=False)
    created_at = Column(DateTime(timezone=True), default=func.now())

    # связи
    blacklisted = relationship("Blacklist",
                               back_populates="candidate",
                               cascade="all, delete-orphan")
    favorites = relationship("Favorite",
                             back_populates="candidate",
                             cascade="all, delete-orphan")
    search_history = relationship("SearchHistory",
                                  back_populates="candidate",
                                  cascade="all, delete-orphan")
    __table_args__ = (
        CheckConstraint('sex IN (0, 1, 2)', name='check_candidate_sex'),
        Index('idx_candidates_city', 'city'),
        Index('idx_candidates_sex', 'sex'),
        Index('idx_candidates_has_photo', 'has_photo'),
    )

    def __repr__(self):
        return f"<Candidate(candidate_id={self.candidate_id}, first_name={self.first_name}, last_name={self.last_name})>"


class Blacklist(Base):
    """Модель списка блокировки.

    Связывает пользователя и кандидата, которого он добавил в чёрный список.
    """
    __tablename__ = 'blacklist'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    candidate_id = Column(Integer, ForeignKey('candidates.candidate_id', ondelete='CASCADE'), nullable=False)
    blocked_at = Column(DateTime(timezone=True), server_default=func.now())

    #Связи
    user = relationship("User", back_populates="blacklisted")
    candidate = relationship("Candidate", back_populates="blacklisted")

    __table_args__ = (
        UniqueConstraint('user_id', 'candidate_id', name='unique_blacklist_user_candidate'),
        Index('idx_blacklist_user', 'user_id'),
    )

    def __repr__(self):
        return f"<Blacklist(user_id={self.user_id}, candidate_id={self.candidate_id})>"


class Favorite(Base):
    """Модель избранного.

    Связывает пользователя и кандидата, которого он добавил в избранное.
    """
    __tablename__ = 'favorites'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    candidate_id = Column(Integer, ForeignKey('candidates.candidate_id', ondelete='CASCADE'), nullable=False)
    added_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)

    user = relationship("User", back_populates="favorites")
    candidate = relationship("Candidate", back_populates="favorites")

    __table_args__ = (
        UniqueConstraint('user_id', 'candidate_id', name='unique_favorite_user_candidate'),
        Index('idx_favorite_user', 'user_id'),
    )

    def __repr__(self):
        return f"<Favorite(user_id={self.user_id}, candidate_id={self.candidate_id})>"


class SearchHistory(Base):
    """Модель истории просмотров.

    Фиксирует, какие кандидаты были показаны пользователю и какую реакцию он оставил.
    """
    __tablename__ = 'search_history'
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey('users.user_id', ondelete='CASCADE'), nullable=False)
    candidate_id = Column(Integer, ForeignKey('candidates.candidate_id', ondelete='CASCADE'), nullable=False)
    shown_at = Column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    reaction = Column(String(50), nullable=True) # 'licked', 'blocked', NULL

    # Связи
    user = relationship("User", back_populates="search_history")
    candidate = relationship("Candidate", back_populates="search_history")

    __table_args__ = (
        CheckConstraint("reaction IN ('licked', 'blocked') OR reaction IS NULL",
                        name='check_reaction'),
        UniqueConstraint('user_id', 'candidate_id', name='unique_search_history_user_candidate'),
        Index('idx_search_history_user', 'user_id', 'candidate_id'),
        Index('idx_search_history_shown_at', 'shown_at'),
    )

    def __repr__(self):
        return f"<SearchHistory(user_id={self.user_id}, candidate_id={self.candidate_id}, reaction={self.reaction})>"


class DatabaseManager:
    """Менеджер подключения и сессий к базе данных.

    Использует SQLAlchemy для управления соединением и сессиями.
    """
    def __init__(self, database_url: Optional[str] = None):
        """Инициализирует менеджер базы данных.

        Если URL не передан, использует значение из конфигурации.

        Args:
            database_url: Строка подключения к PostgreSQL.
        """
        if database_url is None:
            database_url = Config.POSTGRES_URI

        self.engine = create_engine(database_url, echo=False)
        self.Session = sessionmaker(bind=self.engine)

    def create_tables(self) -> None:
        """Создаёт все таблицы в базе данных, если они ещё не существуют.

        Вызывает Base.metadata.create_all для создания всех моделей.
        """
        Base.metadata.create_all(self.engine)
        print('Таблицы созданы успешно')

    def drop_tables(self) -> None:
        """Удаляет все таблицы из базы данных.

        Полностью очищает схему, удаляя все таблицы, связанные с моделями.
        """
        Base.metadata.drop_all(self.engine)
        print('Все таблицы удалены')

    def get_session(self) -> Session:
        """Возвращает новую сессию SQLAlchemy для работы с базой данных.

        Returns:
            Объект сессии, готовый к использованию.
        """
        return self.Session()


if __name__ == "__main__":
    db_manager = DatabaseManager()
    db_manager.create_tables()
