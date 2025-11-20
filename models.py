from sqlalchemy import Column, Integer, String, DateTime
from sqlalchemy.orm import declarative_base
from datetime import datetime

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    fullname = Column(String)
    balance = Column(Integer, default=0)
    last_reward_time = Column(DateTime, nullable=True)
    last_task_time = Column(DateTime, nullable=True)
