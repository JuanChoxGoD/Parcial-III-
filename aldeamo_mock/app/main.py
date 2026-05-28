import os
import logging
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel

# Configurar logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("AldeamoMock")

app = FastAPI(
    title="Aldeamo SMS Provider Mock",
    description="Simulador del proveedor SMS principal Aldeamo.",
    version="1.0.0"
)

class SMSRequest(BaseModel):
    user_id: str
    phone: str
    otp: str

@app.get("/health")
def health():
    return {"status": "ok", "service": "aldeamo_mock"}

@app.post("/sms/send")
def send_sms(payload: SMSRequest):
    """
    Simula el envío de un SMS.
    Si ALDEAMO_FAIL=true en las variables de entorno, responde con 500 Internal Server Error.
    De lo contrario, responde 200 OK.
    """
    fail_flag = os.getenv("ALDEAMO_FAIL", "false").lower()
    
    logger.info(f"Petición de SMS recibida en Aldeamo: para {payload.phone}, OTP: {payload.otp}")
    
    if fail_flag == "true":
        logger.error("ALDEAMO_FAIL está activo. Simulando error 500 en Aldeamo...")
        raise HTTPException(
            status_code=500, 
            detail="Fallo interno simulado en el proveedor principal Aldeamo."
        )
        
    logger.info("Envío de SMS completado exitosamente por Aldeamo.")
    return {
        "status": "success",
        "provider": "aldeamo",
        "message": "SMS sent successfully via Aldeamo."
    }
