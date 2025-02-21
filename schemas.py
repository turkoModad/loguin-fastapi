from pydantic import BaseModel

class User(BaseModel):
    username: str 
    firstname: str
    lastname: str
    country: str
    password_user: str
    email: str
    rol: str
      

class Token(BaseModel):
    access_token: str
    token_type: str

class TokenData(BaseModel):
    username: str | None = None
    
class Login(BaseModel):
    username: str
    password_user: str
