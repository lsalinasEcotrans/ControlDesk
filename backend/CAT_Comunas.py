from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel

router = APIRouter(
    prefix="/cat-comunas",
    tags=["CAT - Comunas"]
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

        print(
            f"❌ Error conectando a la base de datos: {e}"
        )

        return None


# ===============================
# MODELS
# ===============================

class ComunaCreate(BaseModel):
    region_id: int
    codigo_comuna: str
    nombre: str
    activo: bool = True


class ComunaUpdate(BaseModel):
    region_id: Optional[int] = None
    codigo_comuna: Optional[str] = None
    nombre: Optional[str] = None
    activo: Optional[bool] = None


# ===============================
# GET ALL
# ===============================

@router.get("/")
def get_comunas(
    region_id: Optional[int] = None,
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

        query = """
            SELECT
                c.id,
                c.region_id,
                r.codigo_region,
                r.nombre AS region,
                c.codigo_comuna,
                c.nombre,
                c.activo
            FROM CAT_COMUNAS c
            INNER JOIN CAT_REGIONES r
                ON r.id = c.region_id
            WHERE 1 = 1
        """

        params = []

        if region_id is not None:

            query += """
                AND c.region_id = %s
            """

            params.append(region_id)

        if activos is not None:

            query += """
                AND c.activo = %s
            """

            params.append(activos)

        query += """
            ORDER BY c.nombre
        """

        cursor.execute(
            query,
            tuple(params)
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

@router.get("/{comuna_id}")
def get_comuna(comuna_id: int):

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
                c.id,
                c.region_id,
                r.codigo_region,
                r.nombre AS region,
                c.codigo_comuna,
                c.nombre,
                c.activo
            FROM CAT_COMUNAS c
            INNER JOIN CAT_REGIONES r
                ON r.id = c.region_id
            WHERE c.id = %s
            """,
            (comuna_id,)
        )

        comuna = cursor.fetchone()

        if not comuna:

            raise HTTPException(
                status_code=404,
                detail="Comuna no encontrada"
            )

        return comuna

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
def crear_comuna(data: ComunaCreate):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error DB"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        # Validar región
        cursor.execute(
            """
            SELECT id
            FROM CAT_REGIONES
            WHERE id = %s
            """,
            (data.region_id,)
        )

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Región no existe"
            )

        # Validar duplicado
        cursor.execute(
            """
            SELECT id
            FROM CAT_COMUNAS
            WHERE codigo_comuna = %s
               OR (
                    region_id = %s
                    AND nombre = %s
               )
            """,
            (
                data.codigo_comuna,
                data.region_id,
                data.nombre
            )
        )

        if cursor.fetchone():

            raise HTTPException(
                status_code=400,
                detail="La comuna ya existe"
            )

        cursor.execute(
            """
            INSERT INTO CAT_COMUNAS
            (
                region_id,
                codigo_comuna,
                nombre,
                activo
            )
            VALUES (%s, %s, %s, %s)
            """,
            (
                data.region_id,
                data.codigo_comuna,
                data.nombre,
                data.activo
            )
        )

        conn.commit()

        return {
            "message": "Comuna creada correctamente",
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

@router.put("/{comuna_id}")
def actualizar_comuna(
    comuna_id: int,
    data: ComunaUpdate
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
            FROM CAT_COMUNAS
            WHERE id = %s
            """,
            (comuna_id,)
        )

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Comuna no encontrada"
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
        values.append(comuna_id)

        cursor.execute(
            f"""
            UPDATE CAT_COMUNAS
            SET {set_clause}
            WHERE id = %s
            """,
            values
        )

        conn.commit()

        return {
            "message": "Comuna actualizada correctamente"
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

@router.delete("/{comuna_id}")
def eliminar_comuna(comuna_id: int):

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
            FROM CAT_COMUNAS
            WHERE id = %s
            """,
            (comuna_id,)
        )

        if not cursor.fetchone():

            raise HTTPException(
                status_code=404,
                detail="Comuna no encontrada"
            )

        cursor.execute(
            """
            DELETE FROM CAT_COMUNAS
            WHERE id = %s
            """,
            (comuna_id,)
        )

        conn.commit()

        return {
            "message": "Comuna eliminada correctamente"
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