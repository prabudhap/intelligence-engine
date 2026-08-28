import os
from concurrent.futures import ThreadPoolExecutor

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "secure_password_123")

# Security configuration
API_SECRET_KEY = os.getenv("API_SECRET_KEY", None)
ALLOWED_ORIGINS = os.getenv("ALLOWED_ORIGINS", "*").split(",")

# Global background tasks executor
bg_executor = ThreadPoolExecutor(max_workers=4)
