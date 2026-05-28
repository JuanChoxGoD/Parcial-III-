import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("TwilioMock")

app = FastAPI(
    title="Twilio SMS Provider Mock",
    description="Simulador del proveedor SMS fallback Twilio.",
    version="1.0.0"
)

class SMSRequest(BaseModel):
    user_id: str
    phone: str
    otp: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "twilio_mock"}

@app.post("/sms/send")
def send_sms(payload: SMSRequest):
    """
    Simula el envío de un SMS.
    Si TWILIO_FAIL=true en las variables de entorno, responde con 500 Internal Server Error.
    De lo contrario, responde 200 OK.
    """
    fail_flag = os.getenv("TWILIO_FAIL", "false").lower()
    
    logger.info(f"Petición de SMS recibida en Twilio (Fallback): para {payload.phone}, OTP: {payload.otp}")
    
    if fail_flag == "true":
        logger.error("TWILIO_FAIL está activo. Simulando error 500 en Twilio...")
        raise HTTPException(
            status_code=500, 
            detail="Fallo interno simulado en el proveedor fallback Twilio."
        )
        
    logger.info("Envío de SMS completado exitosamente por Twilio.")
    return {
        "status": "success",
        "provider": "twilio",
        "message": "SMS sent successfully via Twilio (Fallback)."
    }
