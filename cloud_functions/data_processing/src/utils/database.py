import os

import psycopg

from src.utils.logger import Logger

logger = Logger()

def get_connection():
  try:
    DB_USER = os.environ.get("DB_USER", None)
    DB_PASSWORD = os.environ.get("DB_PASSWORD", None)
    DB_NAME = os.environ.get("DB_NAME", None)

    if DB_NAME is None or DB_PASSWORD is None or DB_NAME is None:
      raise ValueError("Missing DB Crednetials")
    
    conn = psycopg.connect(dbname={DB_NAME}, user={DB_USER}, password=DB_PASSWORD, host="localhost")

    with conn.cursor as cur:
      cur.execute("""
             SELECT * FROM environment  
        """)
      print("test", cur.fetchall())
    
  except Exception as excep:
    logger.error({"message": "Failed to establish connection with database", "error": str(excep)})