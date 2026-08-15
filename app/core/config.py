import os
from concurrent.futures import ThreadPoolExecutor

NEO4J_URI = os.getenv("NEO4J_URI", "bolt://localhost:7687")
NEO4J_USER = os.getenv("NEO4J_USER", "neo4j")
NEO4J_PASSWORD = os.getenv("NEO4J_PASSWORD", "secure_password_123")

# Global background tasks executor
bg_executor = ThreadPoolExecutor(max_workers=4)
