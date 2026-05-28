# Sistema de Notificaciones OTP — Banco Dhabi 🏦

Este proyecto es una implementación académica de un **Sistema de Notificaciones OTP** diseñado bajo los patrones de arquitectura **CQRS (Command Query Responsibility Segregation)**, **Circuit Breaker** y **Fallback entre Proveedores**. 

El sistema está compuesto por 4 microservicios en Python (FastAPI) y 2 servicios mock que simulan las pasarelas de SMS (Aldeamo como principal y Twilio como fallback), todo orquestado localmente usando **Docker Compose**.

---

## 1. DIAGRAMA DE ARQUITECTURA Y FLUJO

```text
                               +----------------------------+
                               |     CLIENTE DE LA API      |
                               +----------------------------+
                                 |                        ^
                   1. POST /send-otp                      | 2. GET /notifications
                                 |                        |
                                 v                        |
  +-------------------------------------------------------+-------------------------+
  | API GATEWAY (Puerto 8000)                                                       |
  |  * Valida firma y expiración del Token JWT (Secret: dhabi-secret-2024)          |
  |  * Enruta peticiones mediante proxy HTTP reverso (httpx)                        |
  +-------------------------------------------------------+-------------------------+
                                 |                        |
                   Proxy POST    |                        | Proxy GET
                                 v                        v
  +-----------------------------------------+  +------------------------------------+
  | COMMAND SERVICE (Puerto 8001)           |  | QUERY SERVICE (Puerto 8002)        |
  | [LADO ESCRITURA - CQRS]                 |  | [LADO LECTURA - CQRS]              |
  |                                         |  |                                    |
  | 1. Guarda en PostgreSQL (PENDING)       |  | Consulta de forma síncrona en      |
  | 2. Retorna HTTP 202 de inmediato        |  | MongoDB para retornar el historial |
  | 3. Lanza Hilo Background (Worker)       |  | de notificaciones del usuario.     |
  |    * Evalúa Circuit Breaker             |  +------------------------------------+
  |    * Envía SMS a Aldeamo/Twilio         |                             ^
  |    * Actualiza PostgreSQL (SENT/FAILED) |                             |
  |    * Sincroniza asíncronamente con -----+----> Sincroniza Documento   | Lee Historial
  |      MongoDB (Colección read)           |      en MongoDB             |
  +-----------------------------------------+                             |
         |                            |                                   |
         | Intenta Aldeamo            | Twilio (Fallback/OPEN)            |
         v                            v                                   v
  +--------------+             +--------------+                +--------------------+
  | aldeamo_mock |             | twilio_mock  |                |      MongoDB       |
  | (Port 8100)  |             | (Port 8101)  |                |   notifications    |
  +--------------+             +--------------+                +--------------------+
```

---

## 2. REQUISITOS PREVIOS Y INICIO

### Comando para compilar e iniciar todo:
Ejecuta el siguiente comando en la raíz del proyecto para descargar las imágenes, compilar los Dockerfiles locales e iniciar todos los contenedores:

```bash
docker-compose up --build
```

Esto levantará los siguientes servicios en la red Docker:
- **postgres**: Base de datos de escritura (PostgreSQL, puerto interno 5432)
- **mongodb**: Base de datos de lectura (MongoDB, puerto interno 27017)
- **gateway_service**: Proxy único expuesto en el puerto **8000** del host
- **command_service**: Lado escritura (puerto interno 8001)
- **query_service**: Lado lectura (puerto interno 8002)
- **aldeamo_mock**: Mock de Aldeamo (puerto interno 8100)
- **twilio_mock**: Mock de Twilio (puerto interno 8101)

*Nota: Las tablas de PostgreSQL se crean automáticamente al iniciar gracias a SQLAlchemy.*

---

## 3. TOKEN JWT PRE-GENERADO PARA PRUEBAS

Para facilitar las pruebas con `curl` o herramientas como Postman, se ha pre-generado un token JWT válido firmado con el secret `dhabi-secret-2024` y con fecha de expiración en el **año 2050**.

### Token listo para copiar:
```text
eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkaGFiaS1hZG1pbiIsInVzZXJfaWQiOiJ1MTIzIiwicm9sZSI6ImFkbWluIiwiZXhwIjoyNTI0NjA4MDAwfQ.KZg-9J5WKISq08JSjVQUKluWbH9lgVBY_EV1e3T4yL8
```

---

## 4. SECUENCIA DE PRUEBAS EN ORDEN

Abre una nueva terminal en tu equipo host para ejecutar los siguientes comandos `curl`.

### Paso A: Enviar un código OTP (Escritura - Command)
Enviaremos una petición a través del Gateway. El Gateway validará el token y enrutará la petición al `command_service`. El sistema guardará el registro como `PENDING` en PostgreSQL y lanzará un hilo background para completar el envío asíncronamente con Aldeamo (proveedor por defecto en estado `CLOSED`).

```bash
curl -X POST http://localhost:8000/api/v1/send-otp \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkaGFiaS1hZG1pbiIsInVzZXJfaWQiOiJ1MTIzIiwicm9sZSI6ImFkbWluIiwiZXhwIjoyNTI0NjA4MDAwfQ.KZg-9J5WKISq08JSjVQUKluWbH9lgVBY_EV1e3T4yL8" \
  -H "Content-Type: application/json" \
  -d '{"user_id": "u123", "phone": "+573001234567", "otp": "482910"}'
```

*Respuesta esperada (HTTP 202 de inmediato):*
```json
{"notification_id":"<un-uuid-generado>","status":"PENDING"}
```

### Paso B: Consultar el historial del usuario (Lectura - Query)
Consultamos el historial del usuario a través del Gateway. Esta petición se procesa en el `query_service` leyendo directamente **MongoDB** (sin tocar PostgreSQL), demostrando la separación CQRS. Dado que la sincronización es casi instantánea en el hilo background, verás el estado actualizado a `SENT` y con el proveedor `aldeamo`.

```bash
curl -X GET http://localhost:8000/api/v1/notifications/u123 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkaGFiaS1hZG1pbiIsInVzZXJfaWQiOiJ1MTIzIiwicm9sZSI6ImFkbWluIiwiZXhwIjoyNTI0NjA4MDAwfQ.KZg-9J5WKISq08JSjVQUKluWbH9lgVBY_EV1e3T4yL8"
```

*Respuesta esperada:*
```json
[
  {
    "id": "<uuid>",
    "user_id": "u123",
    "phone": "+573001234567",
    "status": "SENT",
    "provider": "aldeamo",
    "created_at": "2026-05-28T..."
  }
]
```

### Paso C: Verificar los datos directamente en PostgreSQL (Base de Escritura)
Dado que las bases de datos no exponen puertos directamente en el host para cumplir con las restricciones de seguridad, podemos conectarnos por la terminal de forma directa ejecutando `docker exec` en el contenedor:

```bash
docker exec -it dhabi_postgres psql -U dhabi_user -d dhabi_db -c "SELECT id, user_id, phone, otp, status, provider FROM notifications;"
```

### Paso D: Verificar los datos directamente en MongoDB (Base de Lectura - CQRS)
De la misma forma, podemos conectarnos directo al contenedor de MongoDB usando `docker exec` y verificar el documento replicado:

```bash
docker exec -it dhabi_mongodb mongosh dhabi_notifications --eval "db.notifications_read.find().pretty()"
```

---

## 5. CÓMO PROBAR EL CIRCUIT BREAKER Y FALLBACK EN VIVO

Para facilitar el monitoreo, hemos creado un endpoint especial de depuración en el `command_service` para observar el estado del breaker en memoria. (Debido a que el Gateway solo hace proxy de los endpoints del enunciado, puedes consultar este estado directamente dentro del ecosistema Docker o ejecutando peticiones al Gateway de prueba si se habilitase, o inspeccionando los logs de los contenedores). El estado y la transición se imprimen con claridad en los logs de la consola del contenedor de `command_service`.

### PASO 1: Forzar la caída de Aldeamo (Proveedor Principal)
Detendremos el mock de Aldeamo para simular una caída total del servicio:

```bash
docker-compose stop aldeamo_mock
```

*(O alternativamente, si deseas mantener el contenedor arriba pero respondiendo 500: ejecuta `ALDEAMO_FAIL=true docker-compose restart aldeamo_mock`)*

### PASO 2: Enviar 6 peticiones seguidas al endpoint send-otp
Enviaremos peticiones seguidas para acumular fallos en Aldeamo y obligar al Circuit Breaker a pasar al estado `OPEN` (umbral >= 5 fallos):

```bash
# Ejecutar este bloque de curls en tu terminal
for i in {1..6}; do
  curl -X POST http://localhost:8000/api/v1/send-otp \
    -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkaGFiaS1hZG1pbiIsInVzZXJfaWQiOiJ1MTIzIiwicm9sZSI6ImFkbWluIiwiZXhwIjoyNTI0NjA4MDAwfQ.KZg-9J5WKISq08JSjVQUKluWbH9lgVBY_EV1e3T4yL8" \
    -H "Content-Type: application/json" \
    -d '{"user_id": "u123", "phone": "+573001234567", "otp": "99900'$i'"}'
  echo ""
done
```

### PASO 3: Observar logs del `command_service` y verificar transiciones
Mira la terminal donde se está ejecutando `docker-compose`. Verás mensajes detallados del logger del `command_service`:
1. `CircuitBreaker: Falló el envío en Aldeamo. Contador de fallos: 1/5` (y se activa fallback inmediato en Twilio, completando con éxito).
2. `...`
3. Al 5to fallo verás: `CircuitBreaker: Umbral de fallos (5) alcanzado. Transición CLOSED -> OPEN`
4. En el 6to envío verás: `CircuitBreaker: Circuit Breaker está OPEN. Desviando tráfico directamente a Twilio...` (¡Ya no intenta Aldeamo, protegiendo al sistema principal!).

### PASO 4: Verificar historial en PostgreSQL y MongoDB
Consulta las notificaciones en MongoDB para confirmar que los envíos tuvieron éxito pero ahora registran proveedor **twilio**:

```bash
curl -X GET http://localhost:8000/api/v1/notifications/u123 \
  -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkaGFiaS1hZG1pbiIsInVzZXJfaWQiOiJ1MTIzIiwicm9sZSI6ImFkbWluIiwiZXhwIjoyNTI0NjA4MDAwfQ.KZg-9J5WKISq08JSjVQUKluWbH9lgVBY_EV1e3T4yL8"
```

*Verás que las últimas notificaciones tienen `"provider": "twilio"` y `"status": "SENT"`, confirmando la resiliencia del sistema.*

### PASO 5: Restaurar Aldeamo y probar recuperación (HALF_OPEN -> CLOSED)
Restauramos el mock de Aldeamo:

```bash
docker-compose start aldeamo_mock
```

1. **Espera 60 segundos** sin hacer envíos (cooldown de recuperación).
2. Envía **1 petición** adicional de OTP:
   ```bash
   curl -X POST http://localhost:8000/api/v1/send-otp \
     -H "Authorization: Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJkaGFiaS1hZG1pbiIsInVzZXJfaWQiOiJ1MTIzIiwicm9sZSI6ImFkbWluIiwiZXhwIjoyNTI0NjA4MDAwfQ.KZg-9J5WKISq08JSjVQUKluWbH9lgVBY_EV1e3T4yL8" \
     -H "Content-Type: application/json" \
     -d '{"user_id": "u123", "phone": "+573001234567", "otp": "777888"}'
   ```
3. Observa los logs del `command_service`:
   - Al pasar los 60 segundos, el breaker pasa a `HALF_OPEN`.
   - Deja pasar esta petición única a Aldeamo.
   - Como Aldeamo respondió 200 OK exitosamente, el Circuit Breaker registra el éxito y realiza la transición: `CircuitBreaker: Aldeamo recuperado. Transición HALF_OPEN -> CLOSED`
   - El contador se resetea y el flujo normal queda restaurado.

---

## 6. TECNOLOGÍAS Y RESTRICCIONES CUMPLIDAS
- **FastAPI** para todas las APIs HTTP.
- **SQLAlchemy** con **psycopg2** en la base de datos PostgreSQL de escritura.
- **PyMongo** síncrono para la consulta rápida de MongoDB de lectura.
- **httpx** asíncrono para el proxy inverso en el API Gateway.
- **Threading** en segundo plano sin usar Celery/Redis para facilitar su ejecución académica simple.
- **Circuit Breaker** en memoria y thread-safe para control concurrente.