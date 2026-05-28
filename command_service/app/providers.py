import httpx
import logging
from app.config import ALDEAMO_URL, TWILIO_URL

logger = logging.getLogger("Providers")

def send_aldeamo(user_id: str, phone: str, otp: str) -> bool:
    """
    Intenta enviar el SMS a través del servicio Aldeamo (proveedor principal).
    Retorna True si tiene éxito (200 OK), False si falla (cualquier otro código o excepción).
    """
    payload = {
        "user_id": user_id,
        "phone": phone,
        "otp": otp
    }
    try:
        logger.info(f"Enviando OTP a través de ALDEAMO para el usuario {user_id} al teléfono {phone}...")
        response = httpx.post(ALDEAMO_URL, json=payload, timeout=5.0)
        if response.status_code == 200:
            logger.info("Proveedor ALDEAMO completó el envío con éxito.")
            return True
        else:
            logger.warning(f"Proveedor ALDEAMO falló con código HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error de red o conexión al intentar comunicar con ALDEAMO: {str(e)}")
        return False

def send_twilio(user_id: str, phone: str, otp: str) -> bool:
    """
    Intenta enviar el SMS a través del servicio Twilio (proveedor fallback).
    Retorna True si tiene éxito (200 OK), False si falla (cualquier otro código o excepción).
    """
    payload = {
        "user_id": user_id,
        "phone": phone,
        "otp": otp
    }
    try:
        logger.info(f"Enviando OTP a través de TWILIO (Fallback) para el usuario {user_id} al teléfono {phone}...")
        response = httpx.post(TWILIO_URL, json=payload, timeout=5.0)
        if response.status_code == 200:
            logger.info("Proveedor TWILIO completó el envío con éxito.")
            return True
        else:
            logger.warning(f"Proveedor TWILIO falló con código HTTP {response.status_code}: {response.text}")
            return False
    except Exception as e:
        logger.error(f"Error de red o conexión al intentar comunicar con TWILIO: {str(e)}")
        return False
