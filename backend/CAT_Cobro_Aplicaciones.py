from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel


router = APIRouter(
    prefix="/cat-cobro-aplicaciones",
    tags=["CAT - Cobro Aplicaciones"]
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
# SCHEMAS
# ===============================

class CobroAplicacionCreate(BaseModel):
    codigo: str
    nombre: str
    cantidad: float
    unidad_cobro: str = "UF"
    descripcion: Optional[str] = None


class CobroAplicacionUpdate(BaseModel):
    codigo: Optional[str] = None
    nombre: Optional[str] = None
    cantidad: Optional[float] = None
    unidad_cobro: Optional[str] = None
    descripcion: Optional[str] = None
    activo: Optional[bool] = None


# ===============================
# GET - LISTAR
# ===============================

@router.get("/")
def listar_cobros_aplicaciones(
    activos: bool = True
):
    connection = get_db_connection()

    if not connection:
        raise HTTPException(
            status_code=500,
            detail="No se pudo conectar a la base de datos"
        )

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        if activos:
            query = """
                SELECT
                    id,
                    codigo,
                    nombre,
                    cantidad,
                    unidad_cobro,
                    descripcion,
                    activo,
                    created_at,
                    updated_at
                FROM CAT_COBRO_APLICACIONES
                WHERE activo = TRUE
                ORDER BY id ASC
            """

            cursor.execute(query)

        else:
            query = """
                SELECT
                    id,
                    codigo,
                    nombre,
                    cantidad,
                    unidad_cobro,
                    descripcion,
                    activo,
                    created_at,
                    updated_at
                FROM CAT_COBRO_APLICACIONES
                ORDER BY id ASC
            """

            cursor.execute(query)

        return cursor.fetchall()

    except Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener cobros de aplicaciones: {str(e)}"
        )

    finally:
        if cursor:
            cursor.close()

        connection.close()


# ===============================
# GET - POR ID
# ===============================

@router.get("/{id}")
def obtener_cobro_aplicacion(id: int):
    connection = get_db_connection()

    if not connection:
        raise HTTPException(
            status_code=500,
            detail="No se pudo conectar a la base de datos"
        )

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        query = """
            SELECT
                id,
                codigo,
                nombre,
                cantidad,
                unidad_cobro,
                descripcion,
                activo,
                created_at,
                updated_at
            FROM CAT_COBRO_APLICACIONES
            WHERE id = %s
        """

        cursor.execute(query, (id,))

        resultado = cursor.fetchone()

        if not resultado:
            raise HTTPException(
                status_code=404,
                detail="Cobro de aplicación no encontrado"
            )

        return resultado

    except HTTPException:
        raise

    except Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener cobro de aplicación: {str(e)}"
        )

    finally:
        if cursor:
            cursor.close()

        connection.close()


# ===============================
# POST - CREAR
# ===============================

@router.post("/")
def crear_cobro_aplicacion(data: CobroAplicacionCreate):
    connection = get_db_connection()

    if not connection:
        raise HTTPException(
            status_code=500,
            detail="No se pudo conectar a la base de datos"
        )

    cursor = None

    try:
        cursor = connection.cursor()

        # Verificar código existente
        cursor.execute(
            """
            SELECT id
            FROM CAT_COBRO_APLICACIONES
            WHERE codigo = %s
            """,
            (data.codigo,)
        )

        existe = cursor.fetchone()

        if existe:
            raise HTTPException(
                status_code=400,
                detail="El código ya existe"
            )

        query = """
            INSERT INTO CAT_COBRO_APLICACIONES (
                codigo,
                nombre,
                cantidad,
                unidad_cobro,
                descripcion
            )
            VALUES (%s, %s, %s, %s, %s)
        """

        cursor.execute(
            query,
            (
                data.codigo,
                data.nombre,
                data.cantidad,
                data.unidad_cobro,
                data.descripcion
            )
        )

        connection.commit()

        nuevo_id = cursor.lastrowid

        return {
            "message": "Cobro de aplicación creado correctamente",
            "id": nuevo_id
        }

    except HTTPException:
        connection.rollback()
        raise

    except Error as e:
        connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Error al crear cobro de aplicación: {str(e)}"
        )

    finally:
        if cursor:
            cursor.close()

        connection.close()


# ===============================
# PUT - ACTUALIZAR
# ===============================

@router.put("/{id}")
def actualizar_cobro_aplicacion(
    id: int,
    data: CobroAplicacionUpdate
):
    connection = get_db_connection()

    if not connection:
        raise HTTPException(
            status_code=500,
            detail="No se pudo conectar a la base de datos"
        )

    cursor = None

    try:
        cursor = connection.cursor(dictionary=True)

        # Verificar existencia
        cursor.execute(
            """
            SELECT id
            FROM CAT_COBRO_APLICACIONES
            WHERE id = %s
            """,
            (id,)
        )

        existe = cursor.fetchone()

        if not existe:
            raise HTTPException(
                status_code=404,
                detail="Cobro de aplicación no encontrado"
            )

        # Verificar código duplicado
        if data.codigo is not None:

            cursor.execute(
                """
                SELECT id
                FROM CAT_COBRO_APLICACIONES
                WHERE codigo = %s
                  AND id <> %s
                """,
                (data.codigo, id)
            )

            codigo_existe = cursor.fetchone()

            if codigo_existe:
                raise HTTPException(
                    status_code=400,
                    detail="El código ya está siendo utilizado"
                )

        campos = []
        valores = []

        if data.codigo is not None:
            campos.append("codigo = %s")
            valores.append(data.codigo)

        if data.nombre is not None:
            campos.append("nombre = %s")
            valores.append(data.nombre)

        if data.cantidad is not None:
            campos.append("cantidad = %s")
            valores.append(data.cantidad)

        if data.unidad_cobro is not None:
            campos.append("unidad_cobro = %s")
            valores.append(data.unidad_cobro)

        if data.descripcion is not None:
            campos.append("descripcion = %s")
            valores.append(data.descripcion)

        if data.activo is not None:
            campos.append("activo = %s")
            valores.append(data.activo)

        if not campos:
            raise HTTPException(
                status_code=400,
                detail="No hay datos para actualizar"
            )

        valores.append(id)

        query = f"""
            UPDATE CAT_COBRO_APLICACIONES
            SET {", ".join(campos)}
            WHERE id = %s
        """

        cursor.execute(query, tuple(valores))

        connection.commit()

        return {
            "message": "Cobro de aplicación actualizado correctamente",
            "id": id
        }

    except HTTPException:
        connection.rollback()
        raise

    except Error as e:
        connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar cobro de aplicación: {str(e)}"
        )

    finally:
        if cursor:
            cursor.close()

        connection.close()


# ===============================
# DELETE - ELIMINACIÓN LÓGICA
# ===============================

@router.delete("/{id}")
def eliminar_cobro_aplicacion(id: int):
    connection = get_db_connection()

    if not connection:
        raise HTTPException(
            status_code=500,
            detail="No se pudo conectar a la base de datos"
        )

    cursor = None

    try:
        cursor = connection.cursor()

        # Verificar existencia
        cursor.execute(
            """
            SELECT id
            FROM CAT_COBRO_APLICACIONES
            WHERE id = %s
            """,
            (id,)
        )

        existe = cursor.fetchone()

        if not existe:
            raise HTTPException(
                status_code=404,
                detail="Cobro de aplicación no encontrado"
            )

        query = """
            UPDATE CAT_COBRO_APLICACIONES
            SET activo = FALSE
            WHERE id = %s
        """

        cursor.execute(query, (id,))

        connection.commit()

        return {
            "message": "Cobro de aplicación desactivado correctamente",
            "id": id
        }

    except HTTPException:
        connection.rollback()
        raise

    except Error as e:
        connection.rollback()

        raise HTTPException(
            status_code=500,
            detail=f"Error al eliminar cobro de aplicación: {str(e)}"
        )

    finally:
        if cursor:
            cursor.close()

        connection.close()