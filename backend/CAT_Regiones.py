from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel

router = APIRouter(
    prefix="/cat-regiones",
    tags=["CAT - Regiones"]
)

# ===============================
# ENV
# ===============================

DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
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
# MODELS
# ===============================

class RegionCreate(BaseModel):
    codigo_region: str
    nombre: str
    nombre_corto: Optional[str] = None
    activo: bool = True


class RegionUpdate(BaseModel):
    codigo_region: Optional[str] = None
    nombre: Optional[str] = None
    nombre_corto: Optional[str] = None
    activo: Optional[bool] = None


# ===============================
# GET ALL
# ===============================

@router.get("/")
def get_regiones(
    activos: Optional[bool] = None
):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        if activos is None:

            cursor.execute(
                """
                SELECT
                    id,
                    codigo_region,
                    nombre,
                    nombre_corto,
                    activo
                FROM CAT_REGIONES
                ORDER BY nombre
                """
            )

        else:

            cursor.execute(
                """
                SELECT
                    id,
                    codigo_region,
                    nombre,
                    nombre_corto,
                    activo
                FROM CAT_REGIONES
                WHERE activo = %s
                ORDER BY nombre
                """,
                (activos,)
            )

        return cursor.fetchall()

    except Error as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()


# ===============================
# GET BY ID
# ===============================

@router.get("/{region_id}")
def get_region(region_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT
                id,
                codigo_region,
                nombre,
                nombre_corto,
                activo
            FROM CAT_REGIONES
            WHERE id = %s
            """,
            (region_id,)
        )

        region = cursor.fetchone()

        if not region:

            raise HTTPException(
                status_code=404,
                detail="Región no encontrada"
            )

        return region

    except HTTPException:
        raise

    except Error as e:

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()


# ===============================
# CREATE
# ===============================

@router.post("/")
def crear_region(data: RegionCreate):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        cursor.execute(
            """
            SELECT id
            FROM CAT_REGIONES
            WHERE codigo_region = %s
               OR nombre = %s
            """,
            (
                data.codigo_region,
                data.nombre
            )
        )

        if cursor.fetchone():

            raise HTTPException(
                status_code=400,
                detail="La región ya existe"
            )

        cursor.execute(
            """
            INSERT INTO CAT_REGIONES
            (
                codigo_region,
                nombre,
                nombre_corto,
                activo
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                data.codigo_region,
                data.nombre,
                data.nombre_corto,
                data.activo
            )
        )

        conn.commit()

        return {
            "message": "Región creada correctamente",
            "id": cursor.lastrowid
        }

    except HTTPException:

        conn.rollback()
        raise

    except Exception as e:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()


# ===============================
# UPDATE
# ===============================

@router.put("/{region_id}")
def actualizar_region(
    region_id: int,
    data: RegionUpdate
):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        cursor.execute(
            """
            SELECT id
            FROM CAT_REGIONES
            WHERE id = %s
            """,
            (region_id,)
        )

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Región no encontrada"
            )

        fields = data.model_dump(
            exclude_none=True
        )

        if not fields:

            raise HTTPException(
                status_code=400,
                detail="No hay campos para actualizar"
            )

        set_clause = ", ".join(
            [
                f"{key} = %s"
                for key in fields.keys()
            ]
        )

        values = list(fields.values())
        values.append(region_id)

        cursor.execute(
            f"""
            UPDATE CAT_REGIONES
            SET {set_clause}
            WHERE id = %s
            """,
            values
        )

        conn.commit()

        return {
            "message": "Región actualizada correctamente"
        }

    except HTTPException:

        conn.rollback()
        raise

    except Exception as e:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()


# ===============================
# DELETE
# ===============================

@router.delete("/{region_id}")
def eliminar_region(region_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        cursor.execute(
            """
            SELECT id
            FROM CAT_REGIONES
            WHERE id = %s
            """,
            (region_id,)
        )

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Región no encontrada"
            )

        cursor.execute(
            """
            SELECT id
            FROM CAT_COMUNAS
            WHERE region_id = %s
            LIMIT 1
            """,
            (region_id,)
        )

        if cursor.fetchone():

            raise HTTPException(
                status_code=400,
                detail="No se puede eliminar la región porque tiene comunas asociadas"
            )

        cursor.execute(
            """
            DELETE FROM CAT_REGIONES
            WHERE id = %s
            """,
            (region_id,)
        )

        conn.commit()

        return {
            "message": "Región eliminada correctamente"
        }

    except HTTPException:

        conn.rollback()
        raise

    except Exception as e:

        conn.rollback()

        raise HTTPException(
            status_code=500,
            detail=str(e)
        )

    finally:

        cursor.close()
        conn.close()