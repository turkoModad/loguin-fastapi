import random
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from dotenv import load_dotenv
import os
from db.database import get_db
from sqlalchemy.orm import Session
from fastapi import Depends

load_dotenv()


def generar_codigo(user):
    return str(random.randint(100000, 999999))


EMAIL_HOST = os.getenv("EMAIL_HOST")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", 587))
EMAIL_USERNAME = os.getenv("EMAIL_USERNAME")
EMAIL_PASSWORD = os.getenv("EMAIL_PASSWORD")


def send_recovery_email(email: str, codigo: str):
    # Configurar el mensaje
    msg = MIMEMultipart()
    msg['From'] = EMAIL_USERNAME
    msg['To'] = email
    msg['Subject'] = "Recuperación de Contraseña"
    
    body = f"Hola,\n\nTu código de recuperación es: {codigo}\n\nSi no solicitaste la recuperación, ignora este mensaje."
    msg.attach(MIMEText(body, 'plain'))

    try:
        # Conectar al servidor SMTP y enviar el email
        server = smtplib.SMTP(EMAIL_HOST, EMAIL_PORT)
        server.starttls()  # Habilitar TLS para mayor seguridad
        server.login(EMAIL_USERNAME, EMAIL_PASSWORD)
        server.sendmail(EMAIL_USERNAME, email, msg.as_string())
        server.quit()
        print("Email enviado correctamente.")
    except Exception as e:
        print(f"Error al enviar el email: {e}")


def resetear_codigo_recuperacion(user, db: Session = Depends(get_db)):
    user.codigo = None
    user.codigo_expiracion = None
    user.intentos = 0
    db.commit()
    db.refresh(user)
    return user
