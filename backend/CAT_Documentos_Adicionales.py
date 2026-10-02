from fastapi import APIRouter, HTTPException
import mysql.connector
from mysql.connector import Error
import os
from typing import Optional
from pydantic import BaseModel, Field
from datetime import datetime
from enum import Enum

router = APIRouter(
    prefix="/cat-documentos-adicionales",
    tags=["CAT - Documentos Adicionales"]
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
# ENUMS
# ===============================

class TipoFecha(str, Enum):
    SIN_FECHA = "sin_fecha"
    EMISION = "emision"
    EXPIRACION = "expiracion"


# ===============================
# MODELS
# ===============================

class DocumentoAdicionalCreate(BaseModel):
    codigo: str = Field(..., max_length=100)
    nombre: str = Field(..., max_length=200)
    descripcion: Optional[str] = Field(None, max_length=500)
    categoria: str = Field(..., max_length=50)
    obligatorio: bool = False
    tipo_fecha: TipoFecha = TipoFecha.SIN_FECHA
    dias_validacion: Optional[int] = None
    orden: int = 0
    activo: bool = True


class DocumentoAdicionalUpdate(BaseModel):
    codigo: Optional[str] = Field(None, max_length=100)
    nombre: Optional[str] = Field(None, max_length=200)
    descripcion: Optional[str] = Field(None, max_length=500)
    categoria: Optional[str] = Field(None, max_length=50)
    obligatorio: Optional[bool] = None
    tipo_fecha: Optional[TipoFecha] = None
    dias_validacion: Optional[int] = None
    orden: Optional[int] = None
    activo: Optional[bool] = None


class DocumentoAdicionalResponse(BaseModel):
    id_documento: int
    codigo: str
    nombre: str
    descripcion: Optional[str]
    categoria: str
    obligatorio: bool
    tipo_fecha: str
    dias_validacion: Optional[int]
    orden: int
    activo: bool
    fecha_creacion: datetime
    fecha_actualizacion: datetime


# ===============================
# GET ALL
# ===============================
@router.get("/", response_model=list[DocumentoAdicionalResponse])
def listar_documentos(activos: bool = True):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error de conexión a la base de datos"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        if activos:
            cursor.execute(
                """
                SELECT 
                    id_documento,
                    codigo,
                    nombre,
                    descripcion,
                    categoria,
                    obligatorio,
                    tipo_fecha,
                    dias_validacion,
                    orden,
                    activo,
                    fecha_creacion,
                    fecha_actualizacion
                FROM CAT_DOCUMENTOS_ADICIONALES
                WHERE activo = TRUE
                ORDER BY orden ASC, nombre ASC
                """
            )
        else:
            cursor.execute(
                """
                SELECT 
                    id_documento,
                    codigo,
                    nombre,
                    descripcion,
                    categoria,
                    obligatorio,
                    tipo_fecha,
                    dias_validacion,
                    orden,
                    activo,
                    fecha_creacion,
                    fecha_actualizacion
                FROM CAT_DOCUMENTOS_ADICIONALES
                ORDER BY orden ASC, nombre ASC
                """
            )

        resultados = cursor.fetchall()
        
        # Convertir tipo_fecha a string para la respuesta
        for doc in resultados:
            if doc.get('tipo_fecha'):
                doc['tipo_fecha'] = str(doc['tipo_fecha'])
        
        return resultados

    except Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en la consulta: {str(e)}"
        )

    finally:
        cursor.close()
        conn.close()


# ===============================
# GET BY ID
# ===============================
@router.get("/{documento_id}", response_model=DocumentoAdicionalResponse)
def obtener_documento(documento_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error de conexión a la base de datos"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        cursor.execute(
            """
            SELECT 
                id_documento,
                codigo,
                nombre,
                descripcion,
                categoria,
                obligatorio,
                tipo_fecha,
                dias_validacion,
                orden,
                activo,
                fecha_creacion,
                fecha_actualizacion
            FROM CAT_DOCUMENTOS_ADICIONALES
            WHERE id_documento = %s
            """,
            (documento_id,)
        )

        documento = cursor.fetchone()

        if not documento:
            raise HTTPException(
                status_code=404,
                detail="Documento no encontrado"
            )

        # Convertir tipo_fecha a string para la respuesta
        if documento.get('tipo_fecha'):
            documento['tipo_fecha'] = str(documento['tipo_fecha'])

        return documento

    except HTTPException:
        raise

    except Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en la consulta: {str(e)}"
        )

    finally:
        cursor.close()
        conn.close()


# ===============================
# CREATE
# ===============================
@router.post("/", response_model=dict)
def crear_documento(data: DocumentoAdicionalCreate):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error de conexión a la base de datos"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        # ===============================
        # VALIDAR CODIGO DUPLICADO
        # ===============================
        cursor.execute(
            """
            SELECT id_documento
            FROM CAT_DOCUMENTOS_ADICIONALES
            WHERE codigo = %s
            """,
            (data.codigo,)
        )

        if cursor.fetchone():
            raise HTTPException(
                status_code=400,
                detail="El código del documento ya existe"
            )

        # ===============================
        # VALIDAR DIAS_VALIDACION
        # ===============================
        if data.dias_validacion is not None and data.dias_validacion <= 0:
            raise HTTPException(
                status_code=400,
                detail="Los días de validación deben ser mayores a 0"
            )

        # ===============================
        # CREAR
        # ===============================
        cursor.execute(
            """
            INSERT INTO CAT_DOCUMENTOS_ADICIONALES (
                codigo,
                nombre,
                descripcion,
                categoria,
                obligatorio,
                tipo_fecha,
                dias_validacion,
                orden,
                activo
            )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s)
            """,
            (
                data.codigo,
                data.nombre,
                data.descripcion,
                data.categoria,
                data.obligatorio,
                data.tipo_fecha.value if isinstance(data.tipo_fecha, TipoFecha) else data.tipo_fecha,
                data.dias_validacion,
                data.orden,
                data.activo
            )
        )

        documento_id = cursor.lastrowid

        conn.commit()

        return {
            "message": "Documento creado correctamente",
            "id_documento": documento_id,
            "codigo": data.codigo
        }

    except HTTPException:
        conn.rollback()
        raise

    except Error as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al crear el documento: {str(e)}"
        )

    finally:
        cursor.close()
        conn.close()


# ===============================
# UPDATE
# ===============================
@router.put("/{documento_id}", response_model=dict)
def actualizar_documento(
    documento_id: int,
    data: DocumentoAdicionalUpdate
):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error de conexión a la base de datos"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        # ===============================
        # VALIDAR EXISTENCIA
        # ===============================
        cursor.execute(
            """
            SELECT id_documento
            FROM CAT_DOCUMENTOS_ADICIONALES
            WHERE id_documento = %s
            """,
            (documento_id,)
        )

        if not cursor.fetchone():
            raise HTTPException(
                status_code=404,
                detail="Documento no encontrado"
            )

        # ===============================
        # CAMPOS A ACTUALIZAR
        # ===============================
        fields = data.model_dump(exclude_none=True)

        if not fields:
            raise HTTPException(
                status_code=400,
                detail="No hay campos para actualizar"
            )

        # ===============================
        # VALIDAR CODIGO
        # ===============================
        if "codigo" in fields:
            cursor.execute(
                """
                SELECT id_documento
                FROM CAT_DOCUMENTOS_ADICIONALES
                WHERE codigo = %s
                  AND id_documento <> %s
                """,
                (fields["codigo"], documento_id)
            )

            if cursor.fetchone():
                raise HTTPException(
                    status_code=400,
                    detail="El código del documento ya está siendo utilizado"
                )

        # ===============================
        # VALIDAR DIAS_VALIDACION
        # ===============================
        if "dias_validacion" in fields and fields["dias_validacion"] is not None:
            if fields["dias_validacion"] <= 0:
                raise HTTPException(
                    status_code=400,
                    detail="Los días de validación deben ser mayores a 0"
                )

        # ===============================
        # CONVERTIR ENUM A VALOR
        # ===============================
        if "tipo_fecha" in fields and isinstance(fields["tipo_fecha"], TipoFecha):
            fields["tipo_fecha"] = fields["tipo_fecha"].value

        # ===============================
        # UPDATE DINAMICO
        # ===============================
        set_clause = ", ".join([f"{key} = %s" for key in fields.keys()])

        values = list(fields.values())
        values.append(documento_id)

        cursor.execute(
            f"""
            UPDATE CAT_DOCUMENTOS_ADICIONALES
            SET {set_clause}
            WHERE id_documento = %s
            """,
            values
        )

        conn.commit()

        return {
            "message": "Documento actualizado correctamente",
            "id_documento": documento_id
        }

    except HTTPException:
        conn.rollback()
        raise

    except Error as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al actualizar el documento: {str(e)}"
        )

    finally:
        cursor.close()
        conn.close()


# ===============================
# DELETE / DESACTIVAR
# ===============================
@router.delete("/{documento_id}", response_model=dict)
def eliminar_documento(documento_id: int):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error de conexión a la base de datos"
        )

    cursor = conn.cursor()

    try:

        conn.start_transaction()

        # ===============================
        # VALIDAR EXISTENCIA
        # ===============================
        cursor.execute(
            """
            SELECT id_documento, activo, codigo, nombre
            FROM CAT_DOCUMENTOS_ADICIONALES
            WHERE id_documento = %s
            """,
            (documento_id,)
        )

        documento = cursor.fetchone()

        if not documento:
            raise HTTPException(
                status_code=404,
                detail="Documento no encontrado"
            )

        # ===============================
        # DESACTIVAR
        # ===============================
        cursor.execute(
            """
            UPDATE CAT_DOCUMENTOS_ADICIONALES
            SET activo = FALSE
            WHERE id_documento = %s
            """,
            (documento_id,)
        )

        conn.commit()

        return {
            "message": f"Documento '{documento[2]}' desactivado correctamente",
            "id_documento": documento_id,
            "codigo": documento[1]
        }

    except HTTPException:
        conn.rollback()
        raise

    except Error as e:
        conn.rollback()
        raise HTTPException(
            status_code=500,
            detail=f"Error al desactivar el documento: {str(e)}"
        )

    finally:
        cursor.close()
        conn.close()


# ===============================
# GET BY CATEGORY
# ===============================
@router.get("/categoria/{categoria}", response_model=list[DocumentoAdicionalResponse])
def listar_documentos_por_categoria(
    categoria: str,
    activos: bool = True
):

    conn = get_db_connection()

    if not conn:
        raise HTTPException(
            status_code=500,
            detail="Error de conexión a la base de datos"
        )

    cursor = conn.cursor(dictionary=True)

    try:

        query = """
            SELECT 
                id_documento,
                codigo,
                nombre,
                descripcion,
                categoria,
                obligatorio,
                tipo_fecha,
                dias_validacion,
                orden,
                activo,
                fecha_creacion,
                fecha_actualizacion
            FROM CAT_DOCUMENTOS_ADICIONALES
            WHERE categoria = %s
        """
        params = [categoria]

        if activos:
            query += " AND activo = TRUE"
        
        query += " ORDER BY orden ASC, nombre ASC"

        cursor.execute(query, params)

        resultados = cursor.fetchall()
        
        # Convertir tipo_fecha a string para la respuesta
        for doc in resultados:
            if doc.get('tipo_fecha'):
                doc['tipo_fecha'] = str(doc['tipo_fecha'])
        
        return resultados

    except Error as e:
        raise HTTPException(
            status_code=500,
            detail=f"Error en la consulta: {str(e)}"
        )

    finally:
        cursor.close()
        conn.close() 