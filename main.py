from fastapi import FastAPI, Request, Form, Depends, status
import uvicorn
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse, RedirectResponse
from db.database import get_db, Base, engine
from sqlalchemy.orm import Session
from sqlalchemy import and_
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
import time



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


from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException, status

from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request, HTTPException, status

class MiMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        # Definimos las rutas protegidas y el método (POST)
        if request.url.path in ["/admin", "/usuarios"] and request.method == "POST":
            token = request.headers.get("Authorization")
            credentials_exception = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},
            )
            # Si no se envía el token, lanza la excepción
            if not token:
                raise credentials_exception

            # Verifica que tenga el prefijo "Bearer "
            if not token.startswith("Bearer "):
                raise credentials_exception

            # Extrae el token
            token = token.split(" ")[1]
            # Verifica que el token tenga tres partes separadas por puntos (formato JWT)
            if len(token.split(".")) != 3:
                raise credentials_exception

            # Si la verificación del token falla, lanza la excepción
            if not verify_token(token, credentials_exception):
                raise credentials_exception

        # Si no se cumple la condición (por ejemplo, GET o rutas no protegidas), continúa
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
    if autenticacion:        
        user = db.query(models.User).filter(models.User.username == usuario.username).first()
        autenticacion['username'] = usuario.username
        autenticacion['rol'] = user.rol
        if not user:
            raise HTTPException(status_code=404, detail="User not found")    
    return autenticacion  


@app.get("/forgot", response_class=HTMLResponse)
async def forgot(request: Request):
    return templates.TemplateResponse("forgot.html", {"request": request})
    

@app.post("/forgot")
async def forgot(email: str = Form(...), db: Session = Depends(get_db)):    
    user = db.query(models.User).filter(models.User.email == email).first()    
    if user:
        if user.codigo_expiracion and user.codigo == None:
            if user.codigo_expiracion < datetime.now(timezone.utc):
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


@app.post("/recuperacion", response_class=HTMLResponse)
async def recuperacion(codigo: str = Form(...), email: str = Form(...), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == email).first()
    if user.codigo == codigo and user.codigo_expiracion > datetime.now(timezone.utc) and user.intentos < 4:
        resetear_codigo_recuperacion(user, db)
        return RedirectResponse(url=f"/cambio?email={email}", status_code=303)
    else:
        user.intentos += 1
        db.commit()
        db.refresh(user)
        if user.intentos > 3:
            resetear_codigo_recuperacion(user, db)
            expiracion = datetime.now(timezone.utc) + timedelta(minutes=60)
            user.codigo_expiracion = expiracion
            db.commit()
            db.refresh(user)
            return RedirectResponse(url="/forgot?message=Has%20superado%20el%20l%C3%ADmite%20de%20intentos.%20Por%20favor,%20intenta%20de%20nuevo%20m%C3%A1s%20tarde.", status_code=303)
        elif user.codigo_expiracion < datetime.now(timezone.utc):
            resetear_codigo_recuperacion(user, db)
            return RedirectResponse(url="/forgot?message=El%20c%C3%B3digo%20ha%20expirado.%20Solicita%20uno%20nuevo.", status_code=303)
        else:    
            return RedirectResponse(url=f"/recuperar?email={email}", status_code=303)
    

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
    print(user.password_user)    
    return RedirectResponse(url="/", status_code=303)

    
@app.get("/usuarios", response_class=HTMLResponse)
async def usuarios(request: Request):                     
    return templates.TemplateResponse("usuarios.html", {"request": request})


@app.post("/usuarios")
async def usuarios(user_global: TokenData = Depends(get_current_user), db: Session = Depends(get_db)):
    datos = db.query(models.User).filter(models.User.username == user_global.username).first()   
    return {'usuario': datos}    


@app.get("/admin", response_class=HTMLResponse)
async def admin(request: Request):          
    return templates.TemplateResponse("admin.html", {"request": request})


@app.post("/admin")
async def admin(db: Session = Depends(get_db)):       
    data = db.query(models.User).all()    
    return {"usuarios": data}    
            

if __name__ == "__main__":
    uvicorn.run('main:app', port=8001, reload=True)