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


# ---------------------------
# ENDPOINT: Obtener todos los headers (usando stored procedure OWA_HEADERS)
# ---------------------------
@router.get("")
def get_headers_with_estado():
    """
    Llama al stored procedure OWA_HEADERS y retorna los resultados.
    - Retorna 500 si falla la conexión o la ejecución del SP.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    # Usamos cursor con dictionary=True para devolver filas como dicts (clave: nombre columna)
    cursor = conn.cursor(dictionary=True)
    
    try:
        # Ejecutar stored procedure
        cursor.callproc('OWA_HEADERS')
        
        # Al usar stored_results() podemos iterar todos los result sets devueltos por el SP.
        results = []
        for result in cursor.stored_results():
            # Si el SP solo devuelve un result set, esto lo cargará en `results`.
            results = result.fetchall()
        
        return results
    except Error as e:
        # Propagar error 500 con mensaje legible para debugging (no incluir datos sensibles)
        raise HTTPException(status_code=500, detail=f"Error ejecutando SP: {e}")
    finally:
        # Liberar recursos siempre
        cursor.close()
        conn.close()


# ---------------------------
# ENDPOINT: Auto-asignar correo a un usuario
# ---------------------------
@router.put("/asignar/{idCorreo}")
def asignar_correo(idCorreo: int, user_id: int = Body(..., embed=True)):
    """
    Llama al SP para actualizar el estado del correo a 3 y asignarlo al usuario.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor()
    try:
        # Llamada al Stored Procedure
        cursor.callproc("OWA_U_ESTADO_ASIGNADO", (user_id, idCorreo))
        conn.commit()

        # MySQL devuelve rowcount solo después de ejecutar un SELECT dentro del SP.
        # Para validar si realmente afectó una fila, usamos cursor.rowcount después del commit.
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Correo no encontrado o no se actualizó")

        return {
            "message": "Correo asignado correctamente",
            "idCorreo": idCorreo
        }

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando SP: {e}")
    finally:
        cursor.close()
        conn.close()


# ---------------------------
# ENDPOINT: Obtener detalle mínimo (idCorreo, idOwa) por idCorreo
# ---------------------------
@router.get("/detalle/{idCorreo}")
def get_header_by_id(idCorreo: int):
    """
    Retorna idCorreo e idOwa desde OWA_HEADERS para un idCorreo dado.
    - 404 si no existe.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)
    try:
        query = """
        SELECT idCorreo, idOwa, conversationId
        FROM OWA_HEADERS
        WHERE idCorreo = %s
        """
        cursor.execute(query, (idCorreo,))
        result = cursor.fetchone()

        if not result:
            raise HTTPException(status_code=404, detail="Correo no encontrado")

        return result
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando consulta: {e}")
    finally:
        cursor.close()
        conn.close()


# ---------------------------
# ENDPOINT: Actualizar estados de forma GENERAL
# ---------------------------
@router.put("/estado/{idCorreo}")
def update_estado_correo(
    idCorreo: int,
    estado: int = Body(..., embed=True)
):
    """
    Cambia el estado de un correo.
    - Recibe el idCorreo por la URL.
    - Recibe el nuevo estado por el body.
    - Reutilizable para cualquier cambio de estado.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor()

    try:
        query = """
        UPDATE OWA_HEADERS
        SET estado = %s
        WHERE idCorreo = %s
        """

        cursor.execute(query, (estado, idCorreo))
        conn.commit()

        return {
            "message": f"Estado actualizado a {estado}",
            "idCorreo": idCorreo
        }

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error actualizando estado: {e}")

    finally:
        cursor.close()
        conn.close()
