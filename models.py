# models.py
from sqlalchemy import Column, Integer, String
from sqlalchemy.ext.declarative import declarative_base

Base = declarative_base()

class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    username = Column(String)
    fullname = Column(String)
    balance = Column(Integer, default=0)

class Invoice(Base):
    __tablename__ = "invoices"

    id = Column(Integer, primary_key=True)
    invoice_id = Column(Integer)
    user_id = Column(Integer)
    pack_id = Column(String)
    status = Column(String)
