from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os

router = APIRouter(prefix="/bodys", tags=["OWA - Bodys"])

DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
DB_SOCKET = os.environ.get("DB_SOCKET")


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


@router.get("/detalle/{idCorreo}")
def get_body_by_id(idCorreo: int):
    """
    Busca un correo por idCorreo en OWA_BODYS y devuelve idCorreo + mensaje_ia.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)
    try:
        query = """
            SELECT content, idCorreo, mensaje_ia
            FROM ecotrans_intranet.OWA_BODYS
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
