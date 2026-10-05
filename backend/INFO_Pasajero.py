from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os

router = APIRouter(prefix="/pasajeros", tags=["INFO - Pasajeros"])

# ===============================
# ENV
# ===============================
DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME_pasajeros")
DB_SOCKET = os.environ.get("DB_SOCKET")


# ===============================
# DB CONNECTION
# ===============================
def get_db_connection():
    try:
        conn = mysql.connector.connect(
            user=DB_USER,
            password=DB_PASS,
            unix_socket=DB_SOCKET,
            database=DB_NAME
        )
        return conn
    except Error as e:
        print(f"❌ Error conectando a la base de datos: {e}")
        return None


# ===============================
# GET ALL PASAJEROS
# ===============================
@router.get("/")
def get_pasajeros():
    """
    Obtiene todos los pasajeros desde INFO_PASAJERO
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)

    try:
        query = """
            SELECT
                id_info,
                auth_id,
                grupo_numero,
                rut,
                nombre,
                contacto,
                rol,
                direccion_origen,
                comuna_origen,
                latitud_origen,
                longitud_origen,
                hora_programada,
                direccion_destino,
                latitud_destino,
                longitud_destino,
                created_at,
                updated_at
            FROM INFO_PASAJERO
        """
        cursor.execute(query)
        result = cursor.fetchall()

        return result

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando consulta: {e}")

    finally:
        cursor.close()
        conn.close()


# ===============================
# GET PASAJEROS BY AUTH_ID
# ===============================
@router.get("/auth/{auth_id}")
def get_pasajeros_by_auth(auth_id: int):
    """
    Obtiene pasajeros asociados a un auth_id
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)

    try:
        query = """
            SELECT
                id_info,
                auth_id,
                grupo_numero,
                rut,
                nombre,
                contacto,
                rol,
                direccion_origen,
                comuna_origen,
                latitud_origen,
                longitud_origen,
                hora_programada,
                direccion_destino,
                latitud_destino,
                longitud_destino,
                created_at,
                updated_at
            FROM INFO_PASAJERO
            WHERE auth_id = %s
        """
        cursor.execute(query, (auth_id,))
        result = cursor.fetchall()

        if not result:
            raise HTTPException(
                status_code=404,
                detail="No se encontraron pasajeros para este auth_id"
            )

        return result

    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando consulta: {e}")

    finally:
        cursor.close()
        conn.close()
