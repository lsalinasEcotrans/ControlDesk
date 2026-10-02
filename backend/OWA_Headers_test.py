from fastapi import APIRouter, HTTPException, Body, WebSocket
import mysql.connector
from mysql.connector import Error
import os
import json
import time

router = APIRouter(prefix="/headers_v1", tags=["OWA - Headers"])

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


# ---------------------------
# ENDPOINTS EXISTENTE
# ---------------------------

@router.get("")
def get_headers_with_estado():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)
    
    try:
        # Llamar al stored procedure
        cursor.callproc('OWA_HEADERS')
        
        # Obtener los resultados
        # stored_results() devuelve un generador con todos los result sets
        results = []
        for result in cursor.stored_results():
            results = result.fetchall()
        
        return results
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando SP: {e}")
    finally:
        cursor.close()
        conn.close()

# ---------------------------
# ENDPOINTS EXISTENTE con websocket
# ---------------------------
@router.websocket("/ws")
async def ws_headers(websocket: WebSocket):

    await websocket.accept()
    ultimo_hash = None

    while True:
        conn = get_db_connection()
        cursor = conn.cursor(dictionary=True)
        cursor.callproc("OWA_HEADERS")

        data = []
        for result in cursor.stored_results():
            data = result.fetchall()

        cursor.close()
        conn.close()

        # Calcular hash
        nuevo_hash = hash(json.dumps(data, default=str))

        if nuevo_hash != ultimo_hash:
            await websocket.send_json(data)
            ultimo_hash = nuevo_hash

        await asyncio.sleep(3)


# ---------------------------
# NUEVO ENDPOINT: auto-asignar correo
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

@router.get("/detalle/{idCorreo}")
def get_header_by_id(idCorreo: int):
    """
    Busca un correo por su idCorreo en OWA_HEADERS y devuelve su idOwa.
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="Error conectando a la base de datos")

    cursor = conn.cursor(dictionary=True)
    try:
        query = """
        SELECT 
            idCorreo,
            idOwa
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


