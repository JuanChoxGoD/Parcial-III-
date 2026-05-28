from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pymongo import MongoClient
from app.config import MONGODB_URL, MONGODB_DB

app = FastAPI(
    title="Banco Dhabi - Query Service (CQRS)",
    description="Servicio de Lectura. Consulta exclusivamente MongoDB (colección notifications_read) de forma síncrona.",
    version="1.0.0"
)

def get_mongo_collection():
    """
    Establece la conexión a MongoDB y retorna la colección de lectura.
    """
    client = MongoClient(MONGODB_URL, serverSelectionTimeoutMS=5000)
    db = client[MONGODB_DB]
    return db["notifications_read"]

@app.get("/health")
def health():
    return {"status": "ok", "service": "query_service"}

@app.get("/api/v1/notifications/{user_id}", response_class=JSONResponse)
def get_notifications(user_id: str):
    """
    Retorna el historial completo de notificaciones de un usuario dado.
    Consulta únicamente MongoDB (Base de datos de Lectura).
    """
    try:
        collection = get_mongo_collection()
        # Buscar todas las notificaciones para el user_id
        # Ordenamos por created_at de forma descendente para ver los más recientes primero
        cursor = collection.find({"user_id": user_id}).sort("created_at", -1)
        
        notifications_list = []
        for doc in cursor:
            notifications_list.append({
                "id": doc.get("_id"),
                "user_id": doc.get("user_id"),
                "phone": doc.get("phone"),
                "status": doc.get("status"),
                "provider": doc.get("provider"),
                "created_at": doc.get("created_at")
            })
            
        return notifications_list
    except Exception as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error de lectura en MongoDB: {str(e)}"
        )
