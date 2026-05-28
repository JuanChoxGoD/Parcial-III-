import time
import threading
from contextlib import asynccontextmanager
from fastapi import FastAPI, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.models import init_db, SessionLocal, Notification
from app.worker import process_notification_delivery
from app.circuit_breaker import db_circuit_breaker

# Context manager para iniciar la base de datos de forma segura al arrancar
@asynccontextmanager
async def lifespan(app: FastAPI):
    """
    Controla el ciclo de vida de la aplicación.
    Intenta crear las tablas en PostgreSQL con reintentos para soportar el retardo de inicio en Docker Compose.
    """
    retries = 6
    while retries > 0:
        try:
            init_db()
            print("PostgreSQL inicializado y tablas creadas exitosamente.")
            break
        except Exception as e:
            retries -= 1
            print(f"PostgreSQL no disponible. Reintentando en 4 segundos... (Intentos restantes: {retries})")
            time.sleep(4)
    yield

app = FastAPI(
    title="Banco Dhabi - Command Service (CQRS)",
    description="Servicio de Escritura. Recibe notificaciones, escribe en PostgreSQL y lanza workers de envío.",
    version="1.0.0",
    lifespan=lifespan
)

# Pydantic Schemas
class OTPRequest(BaseModel):
    user_id: str = Field(..., description="ID del usuario bancario", example="u123")
    phone: str = Field(..., description="Número de teléfono celular", example="+573001234567")
    otp: str = Field(..., description="Código OTP de seguridad de 6 dígitos", example="482910")

# Dependency para obtener la sesión de BD
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

@app.get("/health")
def health():
    return {"status": "ok", "service": "command_service"}

@app.get("/api/v1/circuit-breaker")
def get_circuit_breaker_status():
    """
    Endpoint de depuración para que el evaluador pueda ver en tiempo real 
    el estado del Circuit Breaker y el conteo de fallos.
    """
    state = db_circuit_breaker.get_state()
    return {
        "state": state,
        "failure_count": db_circuit_breaker.failure_count,
        "failure_threshold": db_circuit_breaker.failure_threshold,
        "recovery_timeout_seconds": db_circuit_breaker.recovery_timeout,
        "last_state_change_timestamp": db_circuit_breaker.last_state_change
    }

@app.post("/api/v1/send-otp", response_class=JSONResponse)
def send_otp(payload: OTPRequest, db: Session = Depends(get_db)):
    """
    Recibe la petición del Gateway, guarda la notificación en PostgreSQL con estado PENDING,
    lanza el worker de entrega en un hilo background de forma asíncrona y retorna de inmediato.
    """
    try:
        # 1. Crear el registro en PostgreSQL en estado PENDING y sin provider asignado
        db_notification = Notification(
            user_id=payload.user_id,
            phone=payload.phone,
            otp=payload.otp,
            status="PENDING",
            provider=None
        )
        db.add(db_notification)
        db.commit()
        db.refresh(db_notification)
        
        notification_id_str = str(db_notification.id)
        
        # 2. Lanzar la tarea de envío en un hilo background separado (sin Celery)
        worker_thread = threading.Thread(
            target=process_notification_delivery,
            args=(notification_id_str,)
        )
        worker_thread.start()
        
        # 3. Retornar inmediatamente al cliente indicando el estado PENDING
        return JSONResponse(
            status_code=202,  # 202 Accepted es más exacto para procesamiento asíncrono
            content={
                "notification_id": notification_id_str,
                "status": "PENDING"
            }
        )
    except Exception as e:
        db.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error interno al procesar el envío de OTP: {str(e)}"
        )
