from db.database import Base, engine
from sqlalchemy import Column, Integer, String


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True)
    firstname = Column(String)
    lastname = Column(String)
    country = Column(String)
    password_user = Column(String)
    email = Column(String, unique=True, index=True, nullable=False)
    rol = Column(String, default="user")