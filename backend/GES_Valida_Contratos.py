from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
import json
from typing import Optional, List
from pydantic import BaseModel
import secrets


router = APIRouter(
    prefix="/ges-valida-contratos",
    tags=["GES - Valida Contratos"]
)

# ===============================
# ENV
# ===============================

DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
DB_SOCKET = os.environ.get("DB_SOCKET")
DB_HOST = os.environ.get("DB_HOST")
DB_PORT = os.environ.get("DB_PORT")

# ===============================
# DB CONNECTION
# ===============================


def get_db_connection():

    """
    Obtiene una conexión a la base de datos.
    Devuelve None si hay un error (el caller debe manejarlo).
    """
    try:
        if DB_SOCKET:
            # Cloud Run / Cloud SQL
            conn = mysql.connector.connect(
                user=DB_USER,
                password=DB_PASS,
                unix_socket=DB_SOCKET,
                database=DB_NAME
            )
        else:
            # Desarrollo local Windows
            conn = mysql.connector.connect(
                user=DB_USER,
                password=DB_PASS,
                host=DB_HOST,
                port=DB_PORT,
                database=DB_NAME
            )
        return conn
    except Error as e:
        print("Error al conectar a la base de datos:", e)
        return None
        
# ===============================
# GET ALL
# ===============================

@router.get("/Genera")
def generar_otp(
    id_contrato: int,
    id_usuario: int
):
    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.callproc(
            "SP_GES_CONTRATO_GENERAR_OTP",
            (id_contrato, id_usuario)
        )
        conn.commit()
        resultado = None

        for result in cursor.stored_results():
            resultado = result.fetchone()

        if not resultado:
            raise HTTPException(
                status_code=500,
                detail="No se pudo generar el OTP"
            )

        return resultado

    except Error as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()

@router.get("/Valida")
def validar_otp(
    codigo_otp: str
):
    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.callproc(
            "SP_GES_CONTRATO_VALIDAR_OTP",
            (codigo_otp,)
        )

        conn.commit()

        resultado = None

        for result in cursor.stored_results():
            resultado = result.fetchone()

        if not resultado:
            raise HTTPException(
                status_code=500,
                detail="No se pudo validar el OTP"
            )

        return resultado

    except Error as e:

        conn.rollback()

        if e.errno == 1644:
            raise HTTPException(
                status_code=400,
                detail=str(e.msg)
            )

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()
