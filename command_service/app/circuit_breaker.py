import time
import threading
import logging

# Configurar logging para ver las transiciones de estado claramente
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("CircuitBreaker")

class CircuitBreakerState:
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"

class CircuitBreaker:
    _instance = None
    _lock = threading.Lock()

    def __new__(cls, *args, **kwargs):
        """
        Patrón Singleton thread-safe para que viva en memoria en el command_service.
        """
        with cls._lock:
            if not cls._instance:
                cls._instance = super(CircuitBreaker, cls).__new__(cls)
                cls._instance._initialized = False
            return cls._instance

    def __init__(self, failure_threshold=5, recovery_timeout=60):
        if self._initialized:
            return
        self.failure_threshold = failure_threshold
        self.recovery_timeout = recovery_timeout
        self.state = CircuitBreakerState.CLOSED
        self.failure_count = 0
        self.last_state_change = 0.0
        self.lock = threading.Lock()
        self._initialized = True
        logger.info("CircuitBreaker inicializado en estado CLOSED.")

    def get_state(self) -> str:
        """
        Consulta el estado del circuito. 
        Si el estado es OPEN y ya pasaron los 60 segundos (recovery_timeout), 
        hace la transición automática a HALF_OPEN.
        """
        with self.lock:
            if self.state == CircuitBreakerState.OPEN:
                elapsed = time.time() - self.last_state_change
                if elapsed >= self.recovery_timeout:
                    logger.info(
                        f"CircuitBreaker: Han transcurrido {elapsed:.1f}s en OPEN. "
                        "Transición automática a HALF_OPEN"
                    )
                    self.state = CircuitBreakerState.HALF_OPEN
            return self.state

    def record_success(self):
        """
        Registra un envío exitoso en Aldeamo.
        Si estábamos en HALF_OPEN, el circuito vuelve a cerrarse (CLOSED).
        """
        with self.lock:
            logger.info("CircuitBreaker: Conexión exitosa con Aldeamo.")
            if self.state == CircuitBreakerState.HALF_OPEN:
                logger.info("CircuitBreaker: Aldeamo recuperado. Transición HALF_OPEN -> CLOSED")
                self.state = CircuitBreakerState.CLOSED
            self.failure_count = 0

    def record_failure(self):
        """
        Registra un fallo de envío por Aldeamo.
        - En CLOSED: Incrementa fallos. Si llega al umbral (>=5), pasa a OPEN.
        - En HALF_OPEN: Pasa inmediatamente a OPEN (re-inicia cooldown).
        """
        with self.lock:
            self.failure_count += 1
            logger.warning(
                f"CircuitBreaker: Falló el envío en Aldeamo. "
                f"Contador de fallos: {self.failure_count}/{self.failure_threshold}"
            )
            
            if self.state == CircuitBreakerState.CLOSED:
                if self.failure_count >= self.failure_threshold:
                    logger.error(
                        f"CircuitBreaker: Umbral de fallos ({self.failure_threshold}) "
                        "alcanzado. Transición CLOSED -> OPEN"
                    )
                    self.state = CircuitBreakerState.OPEN
                    self.last_state_change = time.time()
            elif self.state == CircuitBreakerState.HALF_OPEN:
                logger.error(
                    "CircuitBreaker: Fallo detectado en estado HALF_OPEN. "
                    "Transición inmediata a OPEN"
                )
                self.state = CircuitBreakerState.OPEN
                self.last_state_change = time.time()
                self.failure_count = 1  # Inicializar contador de fallos para la nueva caída

# Instancia singleton global
db_circuit_breaker = CircuitBreaker()
