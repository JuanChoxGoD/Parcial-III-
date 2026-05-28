import os

JWT_SECRET = os.getenv("DHABI_JWT_SECRET", "dhabi-secret-2024")
COMMAND_URL = os.getenv("COMMAND_URL", "http://command_service:8001")
QUERY_URL = os.getenv("QUERY_URL", "http://query_service:8002")
