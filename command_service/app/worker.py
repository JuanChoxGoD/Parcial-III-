import logging
from pymongo import MongoClient
from app.models import SessionLocal, Notification
from app.circuit_breaker import db_circuit_breaker, CircuitBreakerState
from app.providers import send_aldeamo, send_twilio
from app.config import MONGODB_URL, MONGODB_DB

logger = logging.getLogger("BackgroundWorker")

def get_mongo_collection():
    """
    Establece la conexión a MongoDB y retorna la colección de lectura.
    Se conecta en caliente para tolerar retrasos de inicio del contenedor.
    """
    client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DB]
    return db["notifications_read"]

def process_notification_delivery(notification_id: str):
    """
    Lógica de envío asíncrono ejecutada en un hilo background.
    Implementa:
    1. Lectura en PostgreSQL
    2. Evaluación de Circuit Breaker
    3. Envío al mock correspondiente (con fallback si aplica)
    4. Guardado del resultado en PostgreSQL (SENT / FAILED)
    5. Sincronización asíncrona hacia MongoDB (CQRS)
    """
    logger.info(f"Worker iniciado para procesar notificación ID: {notification_id}")
    db_session = SessionLocal()
    try:
        # 1. Recuperar registro de PostgreSQL
        # Convertir a UUID al buscar
        import uuid
        notification_uuid = uuid.UUID(notification_id)
        notification = db_session.query(Notification).filter(Notification.id == notification_uuid).first()
        if not notification:
            logger.error(f"Notificación {notification_id} no fue encontrada en PostgreSQL.")
            return

        # 2. Obtener estado del Circuit Breaker
        state = db_circuit_breaker.get_state()
        logger.info(f"Evaluando Circuit Breaker: Estado actual = {state}")

        sent_successfully = False
        chosen_provider = None

        if state in (CircuitBreakerState.CLOSED, CircuitBreakerState.HALF_OPEN):
            # Intenta enviar por Aldeamo (Principal)
            success = send_aldeamo(notification.user_id, notification.phone, notification.otp)
            if success:
                db_circuit_breaker.record_success()
                sent_successfully = True
                chosen_provider = "aldeamo"
            else:
                db_circuit_breaker.record_failure()
                # Fallback automático e inmediato a Twilio
                logger.warning("Aldeamo ha fallado. Iniciando fallback automático e inmediato por Twilio...")
                success_twilio = send_twilio(notification.user_id, notification.phone, notification.otp)
                if success_twilio:
                    sent_successfully = True
                    chosen_provider = "twilio"
                else:
                    sent_successfully = False
                    chosen_provider = "twilio"

        elif state == CircuitBreakerState.OPEN:
            # Si el circuito está abierto (OPEN), todo va directamente a Twilio
            logger.info("Circuit Breaker está OPEN. Desviando tráfico directamente a Twilio...")
            success = send_twilio(notification.user_id, notification.phone, notification.otp)
            if success:
                sent_successfully = True
                chosen_provider = "twilio"
            else:
                sent_successfully = False
                chosen_provider = "twilio"

        # 3. Actualizar registro en PostgreSQL
        notification.status = "SENT" if sent_successfully else "FAILED"
        notification.provider = chosen_provider
        db_session.commit()
        logger.info(
            f"Registro PostgreSQL actualizado. ID: {notification.id} | "
            f"Status: {notification.status} | Provider: {notification.provider}"
        )

        # 4. Sincronizar documento en MongoDB (Colección de lectura - CQRS)
        try:
            mongo_coll = get_mongo_collection()
            mongo_doc = {
                "_id": str(notification.id),
                "user_id": notification.user_id,
                "phone": notification.phone,
                "status": notification.status,
                "provider": notification.provider,
                "created_at": notification.created_at.isoformat() if notification.created_at else None
            }
            # Upsert en MongoDB
            mongo_coll.replace_one({"_id": mongo_doc["_id"]}, mongo_doc, upsert=True)
            logger.info(f"Documento sincronizado exitosamente en MongoDB. ID: {mongo_doc['_id']}")
        except Exception as mongo_err:
            logger.error(f"Fallo crítico al sincronizar con MongoDB: {str(mongo_err)}")

    except Exception as e:
        logger.error(f"Error inesperado en background worker para notificación {notification_id}: {str(e)}")
        db_session.rollback()
    finally:
        db_session.close()
