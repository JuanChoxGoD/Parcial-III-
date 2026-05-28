import os

MONGODB_URL = os.getenv("MONGODB_URL", "mongodb://mongodb:27017")
MONGODB_DB = os.getenv("MONGODB_DB", "dhabi_notifications")
