import httpx
import jwt
from fastapi import FastAPI, Request, Header, HTTPException, Depends
from fastapi.responses import JSONResponse
from app.config import JWT_SECRET, COMMAND_URL, QUERY_URL

app = FastAPI(
    title="Banco Dhabi - API Gateway",
    description="Único punto de entrada. Valida JWT y hace proxy hacia command_service y query_service.",
    version="1.0.0"
)

def verify_jwt(authorization: str = Header(None)) -> dict:
    """
    Valida que el header Authorization sea un token Bearer firmado con el secret estático.
    """
    if not authorization:
        raise HTTPException(
            status_code=401, 
            detail="Falta el encabezado de autorización (Authorization Header)"
        )
    
    try:
        scheme, token = authorization.split(" ")
        if scheme.lower() != "bearer":
            raise HTTPException(
                status_code=401, 
                detail="El esquema de autenticación debe ser Bearer"
            )
    except ValueError:
        raise HTTPException(
            status_code=401, 
            detail="Formato de encabezado de autorización inválido. Debe ser 'Bearer <token>'"
        )

    try:
        # Decodificar y verificar firma
        payload = jwt.decode(token, JWT_SECRET, algorithms=["HS256"])
        return payload
    except jwt.ExpiredSignatureError:
        raise HTTPException(status_code=401, detail="El token JWT ha expirado")
    except jwt.InvalidTokenError:
        raise HTTPException(status_code=401, detail="Token JWT inválido o firma incorrecta")

@app.get("/health")
def health():
    return {"status": "ok", "service": "gateway_service"}

@app.post("/api/v1/send-otp")
async def send_otp(request: Request, token_payload: dict = Depends(verify_jwt)):
    """
    Recibe la petición de envío de OTP, valida el token JWT y hace proxy
    (HTTP POST) hacia el command_service.
    """
    try:
        body = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Cuerpo de petición JSON inválido")

    async with httpx.AsyncClient() as client:
        try:
            # Proxy request to command_service
            response = await client.post(
                f"{COMMAND_URL}/api/v1/send-otp", 
                json=body, 
                timeout=15.0
            )
            return JSONResponse(
                status_code=response.status_code, 
                content=response.json()
            )
        except httpx.HTTPError as e:
            return JSONResponse(
                status_code=502, 
                content={"detail": f"Error al conectar con command_service: {str(e)}"}
            )

@app.get("/api/v1/notifications/{user_id}")
async def get_notifications(user_id: str, token_payload: dict = Depends(verify_jwt)):
    """
    Recibe la consulta de notificaciones de un usuario, valida el token JWT y hace proxy
    (HTTP GET) hacia el query_service.
    """
    async with httpx.AsyncClient() as client:
        try:
            # Proxy request to query_service
            response = await client.get(
                f"{QUERY_URL}/api/v1/notifications/{user_id}", 
                timeout=15.0
            )
            return JSONResponse(
                status_code=response.status_code, 
                content=response.json()
            )
        except httpx.HTTPError as e:
            return JSONResponse(
                status_code=520, 
                content={"detail": f"Error al conectar con query_service: {str(e)}"}
            )
