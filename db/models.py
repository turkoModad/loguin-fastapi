from db.database import Base, engine
from sqlalchemy import Column, Integer, String, DateTime, Text, TIMESTAMP, ForeignKey, func
from sqlalchemy.orm import relationship


class User(Base):
    __tablename__ = "users"
    id = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username = Column(String, unique=True)
    firstname = Column(String)
    lastname = Column(String)
    country = Column(String)
    password_user = Column(String)
    email = Column(String, unique=True, index=True, nullable=False)
    codigo = Column(String, nullable=True)
    codigo_expiracion = Column(DateTime(timezone=True), nullable=True)
    intentos = Column(Integer, default=0)
    ultimo_intento = Column(DateTime, nullable=True)
    rol = Column(String, default="user")
    mensaje_contacto = relationship("MensajeContacto", back_populates="user")



class MensajeContacto(Base):
    __tablename__ = "mensaje_contacto"
    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), index=True)
    email = Column(String(100), index=True)
    mensaje = Column(Text, nullable=False)
    fecha_mensaje = Column(TIMESTAMP(timezone=True), nullable=False, default=func.now())
    user_id = Column(Integer, ForeignKey('users.id', ondelete="SET NULL"), nullable=True)
    user = relationship("User", back_populates="mensaje_contacto")