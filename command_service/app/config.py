import os

DATABASE_URL = os.getenv(
    "DATABASE_URL", 
    "postgresql://dhabi_user:dhabi_pass@postgres:5432/dhabi_db"
)
MONGODB_URL = os.getenv(
    "MONGODB_URL", 
    "mongodb://mongodb:27017"
)
MONGODB_DB = os.getenv(
    "MONGODB_DB", 
    "dhabi_notifications"
)
ALDEAMO_URL = os.getenv(
    "ALDEAMO_URL", 
    "http://aldeamo_mock:8100/sms/send"
)
TWILIO_URL = os.getenv(
    "TWILIO_URL", 
    "http://twilio_mock:8101/sms/send"
)
