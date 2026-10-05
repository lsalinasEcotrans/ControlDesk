from fastapi import APIRouter, HTTPException, Body
from mysql.connector import pooling, Error
import os
from dotenv import load_dotenv
from pathlib import Path

# Router de FastAPI para agrupar endpoints relacionados con "headers"
router = APIRouter(prefix="/headers", tags=["OWA - Headers"])

# ============================================================
# CARGAR VARIABLES DEL ARCHIVO .env
# ============================================================

BASE_DIR = Path(__file__).resolve().parent
ENV_FILE = BASE_DIR / ".env"

load_dotenv(ENV_FILE)
# ---------------------------
# CONFIGURACIÓN DE LA BASE DE DATOS (variables de entorno)
# ---------------------------
# Se espera que estas variables estén definidas en el entorno de ejecución:
# - DB_USER: usuario MySQL
# - DB_PASS: contraseña MySQL
# - DB_NAME: nombre de la base de datos
# - DB_SOCKET: unix socket (usado en Cloud Run / Unix socket)
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
DB_SOCKET = os.environ.get("DB_SOCKET")
DB_HOST = os.environ.get("DB_HOST")  
DB_PORT = os.environ.get("DB_PORT")  
DB_URL_AUTENTICATHION = os.environ.get("URL_AUTOCAB_AUTENTICATHION")

# ---------------------------
# POOL DE CONEXIONES
# ---------------------------
# Usamos mysql.connector.pooling.MySQLConnectionPool para reusar conexiones y mejorar rendimiento.
# Ajusta pool_size según la concurrencia esperada y los límites del entorno.

if not DB_SOCKET:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=10,
        user=DB_USER,
        password=DB_PASS,
        host=DB_HOST,
        database=DB_NAME
    )
else:
    db_pool = pooling.MySQLConnectionPool(
        pool_name="mypool",
        pool_size=10,
        user=DB_USER,
        password=DB_PASS,
        unix_socket=DB_SOCKET,
        database=DB_NAME
    )

def get_db_connection():
    """
    Obtiene una conexión desde el pool.
    Devuelve None si hay un error (el caller debe manejarlo).
    """
    try:
        return db_pool.get_connection()
    except Error as e:
        # Aquí puedes usar logging en vez de print en producción
        print(f"❌ Error obteniendo conexión del pool: {e}")
        return None