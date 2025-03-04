from fastapi import FastAPI, Request, Form, Depends, status
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from db.database import get_db, Base, engine
from sqlalchemy.orm import Session
from db import models
from passlib.context import CryptContext
from hashing import Hash
from repository import auth
from fastapi.security import OAuth2PasswordRequestForm
from token_jwt import verify_token
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse
from sqlalchemy import inspect
from fastapi.exceptions import HTTPException
from schemas import TokenData
from oauth import get_current_user
from codigo_recuperacion import generar_codigo, send_recovery_email, resetear_codigo_recuperacion
from datetime import datetime, timedelta, timezone
import os
from starlette.status import HTTP_303_SEE_OTHER
import logging


pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")


def create_tables():
    check = inspect(engine)
    existing_tables = check.get_table_names()
    if len(existing_tables) > 0:
        print("Tables already exist")
    else:
        Base.metadata.create_all(bind=engine)

#create_tables()


app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")


#ruta de salud para render
@app.get("/health")
def health_check():
    return {"status": "OK"}


logger = logging.getLogger("main")

class MiMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):        
        rutas_protegidas = ["/admin", "/usuarios"]

        if request.method == "POST" and any(request.url.path.startswith(prefijo) for prefijo in rutas_protegidas):
            token = request.headers.get("Authorization")

            if not token:
                logger.warning("No se envió el token de autenticación.")
                return RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)

            if not token.startswith("Bearer "):
                logger.warning("Token mal formateado: Falta el prefijo 'Bearer '.")
                return RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)

            token = token.split(" ")[1]

            if len(token.split(".")) != 3:
                logger.warning("Token inválido: No tiene tres partes.")
                return RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)
            try:
                credentials_exception = HTTPException(
                    status_code=401,
                    detail="No tienes permisos para esta acción",
                    headers={"WWW-Authenticate": "Bearer"},
                )
                verify_token(token, credentials_exception)

            except Exception as e:
                logger.error(f"Error al verificar token: {e}")
                return RedirectResponse(url="/", status_code=HTTP_303_SEE_OTHER)

        return await call_next(request)

app.add_middleware(MiMiddleware)


@app.get("/", response_class=HTMLResponse)
async def index(request:  Request):
    return templates.TemplateResponse("index.html", {"request": request})


@app.post("/", response_class=HTMLResponse)
async def index(request:  Request):
	return templates.TemplateResponse("index.html", {"request": request})


@app.get("/signup", response_class=HTMLResponse)
async def signup(request: Request):
	return templates.TemplateResponse("signup.html", {"request": request})


@app.post("/signup", response_class=HTMLResponse)
async def signup(username: str = Form(...), password_user: str = Form(...), firstname: str = Form(...), lastname: str = Form(...), country: str = Form(...), email: str = Form(...) ,db: Session = Depends(get_db)):
    password_hash = Hash.hash_password(password_user)
    nuevo_usuario = models.User(
        username=username,
        password_user=password_hash,
        firstname=firstname,
        lastname=lastname,
        country=country,
        email = email,
    )
    db.add(nuevo_usuario)
    db.commit()
    db.refresh(nuevo_usuario)
    return RedirectResponse(url="/")


@app.post("/login", status_code=status.HTTP_200_OK)
async def login(usuario : OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    autenticacion = auth.auth_user(usuario, db)
    if not autenticacion:
        raise HTTPException(status_code=401, detail="Credenciales inválidas")
    user = db.query(models.User).filter(models.User.username == usuario.username).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    autenticacion['username'] = usuario.username
    autenticacion['rol'] = user.rol
    return autenticacion


@app.get("/forgot", response_class=HTMLResponse)
async def forgot(request: Request):
    return templates.TemplateResponse("forgot.html", {"request": request})


@app.post("/forgot")
async def forgot(email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user:
        ahora = datetime.now(timezone.utc)
        if user.codigo and user.codigo_expiracion and user.codigo_expiracion.astimezone(timezone.utc) > ahora:
            return RedirectResponse(
                url=f"/recuperar?email={email}&message=Código%20ya%20enviado.%20Revisa%20tu%20correo.",
                status_code=303
            )
        if user.codigo_expiracion is not None and user.codigo is None:
            if user.codigo_expiracion.astimezone(timezone.utc) < datetime.now(timezone.utc):
                codigo = generar_codigo(user, db)
                send_recovery_email(email, codigo)
                return RedirectResponse(url=f"/recuperar?email={email}", status_code=303)
            else:
                return RedirectResponse(url="/", status_code=303)
        else:
            codigo = generar_codigo(user, db)
            send_recovery_email(email, codigo)

        return RedirectResponse(url=f"/recuperar?email={email}", status_code=303)
    else:
        return RedirectResponse(url=f"/?message=El%20email%20no%20esta%20registrado.", status_code=303)
    

@app.get("/recuperar", response_class=HTMLResponse)
async def recuperar(request: Request):
    return templates.TemplateResponse("recuperar.html", {"request": request, "email": request.query_params.get("email", "")})


@app.post("/recuperacion")
async def recuperacion(codigo: str = Form(...), email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if not user:
        return RedirectResponse(url="/forgot?message=Usuario%20no%20encontrado", status_code=303)

    ahora = datetime.now(timezone.utc)
    
    if user.codigo_expiracion is not None and user.codigo_expiracion.tzinfo is None:
        user.codigo_expiracion = user.codigo_expiracion.replace(tzinfo=timezone.utc)

    if user.codigo == codigo and user.codigo_expiracion > ahora and user.intentos < 4:
        resetear_codigo_recuperacion(user, db)
        return RedirectResponse(url=f"/cambio?email={email}", status_code=303)
    else:
        user.intentos += 1
        db.commit()
        
        if user.intentos >= 4:
            user.codigo_expiracion = ahora + timedelta(hours=1)
            db.commit()
            return RedirectResponse(url="/forgot?message=Bloqueado%20por%201%20hora", status_code=303)
                
    return RedirectResponse(url=f"/recuperar?email={email}&error=Intento%20fallido", status_code=303)



@app.get("/cambio", response_class=HTMLResponse)
async def cambio(request: Request):
    email = request.query_params.get("email", "")
    return templates.TemplateResponse("cambio.html", {"request": request, "email": email})


@app.post("/cambio", response_class=HTMLResponse)
async def cambio_contraseña(password: str = Form(...), email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    user.password_user = Hash.hash_password(password)
    db.commit()
    db.refresh(user)
    return RedirectResponse(url="/", status_code=303)


@app.get("/usuarios", response_class=HTMLResponse)
async def usuarios(request: Request):
    return templates.TemplateResponse("usuarios.html", {"request": request})


@app.post("/usuarios")
async def usuarios(user_global: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    datos = db.query(models.User).filter(models.User.username == user_global.username).first()
    if not datos:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Usuario no encontrado"
        )
    elif datos.rol!= "user":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a esta ruta"
        )
    else:
        return {'usuario': datos}


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):
    return templates.TemplateResponse("admin.html", {"request": request})


@app.post("/admin")
async def admin(user_global: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    datos = db.query(models.User).filter(models.User.username == user_global.username).first()
    if datos.rol!= "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a esta ruta"
        )

    data = db.query(models.User).all()
    if not data:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No hay usuarios en la base de datos"
        )
    return {"usuarios": data}


@app.get("/admin/usuario/{id}")
async def get_user(id: int, db: Session = Depends(get_db), user_global: TokenData = Depends(get_current_user)):   
    datos = db.query(models.User).filter(models.User.username == user_global.username).first()   
    if datos.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a esta ruta"
        )  
    usuario = db.query(models.User).filter(models.User.id == id).first()
    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado")   
    return usuario


@app.post("/admin/usuario/{id}/editar")
async def update_user(id: int, email: str = Form(...), rol: str = Form(...), password : str = Form(...), db: Session = Depends(get_db), user_global: TokenData = Depends(get_current_user)):
    datos = db.query(models.User).filter(models.User.username == user_global.username).first()
    if datos.rol != "admin":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No tienes permisos para acceder a esta ruta"
        )

    usuario = db.query(models.User).filter(models.User.id == id).first()

    if not usuario:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Usuario no encontrado") 

    if email != usuario.email:
        usuario.email = email
    if rol != usuario.rol:
        usuario.rol = rol
    if password != usuario.password_user:
        usuario.password_user = Hash.hash_password(password)

    db.commit()
    db.refresh(usuario)
    return {"message": "Usuario actualizado exitosamente"}


@app.get("/about", response_class=HTMLResponse)
async def about(request: Request):
    return templates.TemplateResponse("about.html", {"request": request})


@app.get("/contacto", response_class=HTMLResponse)
async def contacto(request: Request):
    return templates.TemplateResponse("contacto.html", {"request": request})


@app.post("/contacto", response_class=HTMLResponse)
async def contacto(request : Request, name: str = Form(...), email: str = Form(...), message: str = Form(...), db: Session = Depends(get_db)):
    usuario = db.query(models.User).filter(models.User.email == email).first()

    user_id = usuario.id if usuario else None

    nuevo_mensaje = models.MensajeContacto(
    name = name,
    email = email,
    mensaje = message,
    user_id = user_id  
    )

    db.add(nuevo_mensaje)
    db.commit() 
    db.refresh(nuevo_mensaje)
    return RedirectResponse(url = "/", status_code=HTTP_303_SEE_OTHER)


@app.get("/terminosCondiciones", response_class=HTMLResponse)
async def terminosCondiciones(request: Request):
    return templates.TemplateResponse("terminosCondiciones.html", {"request": request})


@app.get("/politica", response_class=HTMLResponse)
async def politica(request: Request):
    return templates.TemplateResponse("politica.html", {"request": request})


if __name__ == "__main__":
    port = int(os.environ.get("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)