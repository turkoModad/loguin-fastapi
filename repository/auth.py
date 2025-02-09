from sqlalchemy.orm import Session
from db import models
from fastapi import HTTPException, status
from hashing import Hash
from token_jwt import create_access_token


def auth_user(usuario, db: Session):
    user = db.query(models.User).filter(models.User.username == usuario.username).first()
    if not user:
        raise HTTPException(
			status_code=status.HTTP_404_NOT_FOUND,
			detail=f"El Usuario {usuario.username} no fue encontrado"
		)
    if user and not Hash.verify_password(user.password_user, usuario.password):
        raise HTTPException(
			status.HTTP_404_NOT_FOUND, 
			detail="Contraseña incorrecta"
		)
    access_token = create_access_token(
		data={"sub": user.username}
	)
    return {"access_token": access_token, "token_type": "Bearer"}