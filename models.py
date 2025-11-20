from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)      # Telegram user ID
    username = Column(String, nullable=True)    # @username пользователя
    fullname = Column(String, nullable=True)    # Имя и фамилия
    balance = Column(Integer, default=0)        # Баланс монет

    # Новые поля — обязательны!
    last_reward_time = Column(DateTime, nullable=True)  # Когда получал награду
    last_task_time = Column(DateTime, nullable=True)    # Когда получал задание


class Task(Base):
    __tablename__ = "tasks"

    id = Column(Integer, primary_key=True)
    text = Column(String)                       # Содержание задания
