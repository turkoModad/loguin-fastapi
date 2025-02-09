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


class MiMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        if (request.url.path == '/admin' and request.method == 'POST') or (request.url.path == '/usuarios' and request.method == 'POST'):
            token = request.headers.get('Authorization')

            credentials_exception = HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Could not validate credentials",
                headers={"WWW-Authenticate": "Bearer"},)
                                    
            if token:
                if token.startswith("Bearer "):
                    token = token.split(" ")[1]                    
                else:
                    raise credentials_exception
                  
                if len(token.split(".")) != 3:
                    raise credentials_exception 
                                                            
                if verify_token(token, credentials_exception):                    
                                        
                    return await call_next(request)
        else:            
            return await call_next(request) # Avanzar

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
async def signup(username: str = Form(...), password_user: str = Form(...), firstname: str = Form(...), lastname: str = Form(...), country: str = Form(...), db: Session = Depends(get_db)):
    password_hash = Hash.hash_password(password_user)
    nuevo_usuario = models.User(
        username=username, 
        password_user=password_hash, 
        firstname=firstname, 
        lastname=lastname, 
        country=country
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