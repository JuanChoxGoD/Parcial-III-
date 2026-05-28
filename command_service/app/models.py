import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, create_engine
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import sessionmaker, declarative_base
from app.config import DATABASE_URL

Base = declarative_base()

class Notification(Base):
    __tablename__ = "notifications"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(String, nullable=False)
    phone = Column(String, nullable=False)
    otp = Column(String, nullable=False)
    status = Column(String, nullable=False, default="PENDING")  # PENDING | SENT | FAILED
    provider = Column(String, nullable=True)                  # aldeamo | twilio | None
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            "id": str(self.id),
            "user_id": self.user_id,
            "phone": self.phone,
            "otp": self.otp,
            "status": self.status,
            "provider": self.provider,
            "created_at": self.created_at.isoformat() if self.created_at else None,
            "updated_at": self.updated_at.isoformat() if self.updated_at else None,
        }

# Database engine and session setup
engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)

def init_db():
    """
    Crea las tablas en PostgreSQL si no existen.
    Se ejecuta al iniciar el servicio.
    """
    Base.metadata.create_all(bind=engine)
