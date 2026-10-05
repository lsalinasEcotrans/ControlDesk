# ============================================================
# GES_Firmas.py
# ============================================================

import os
import re
import json
import base64
import logging

from datetime import datetime
from typing import Optional, List, Tuple

from fastapi import (
    APIRouter,
    HTTPException,
    Request,
    Response,
    Body,
)

import httpx
import mysql.connector
from mysql.connector import Error


# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("GES - Firmas")


# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/GES_Firmas",
    tags=["GES - Firmas"]
)


# ============================================================
# CONFIGURACIÓN MYSQL
# ============================================================

DB_USER = os.environ.get("DB_USER")
DB_PASS = os.environ.get("DB_PASS")
DB_NAME = os.environ.get("DB_NAME")
DB_SOCKET = os.environ.get("DB_SOCKET")


# ============================================================
# CONFIGURACIÓN ONEDRIVE / MICROSOFT GRAPH
# ============================================================

TENANT_ID = os.environ.get("TENANT_ID", "")
CLIENT_ID = os.environ.get("CLIENT_ID", "")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", "")
USER_EMAIL = os.environ.get("USER_EMAIL", "")

ONEDRIVE_ROOT = "Registros"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_TIMEOUT = 120

TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_URL = "https://graph.microsoft.com/v1.0"


# ============================================================
# CONEXIÓN MYSQL
# ============================================================

def GES_Firmas_Conexion_DB():
    """
    Crea una conexión a MySQL usando socket de Cloud SQL.
    """
    try:
        connection = mysql.connector.connect(
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            unix_socket=DB_SOCKET,
        )

        if not connection.is_connected():
            raise HTTPException(
                status_code=500,
                detail="No fue posible conectar a la base de datos",
            )

        logger.info("Conexión a MySQL establecida correctamente")
        return connection

    except Error as e:
        logger.error(f"Error conexión MySQL: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error de conexión con la base de datos",
        )


# ============================================================
# TOKEN MICROSOFT GRAPH
# ============================================================

async def GES_Firmas_Get_Token() -> str:
    """
    Obtiene el token de Microsoft Graph para trabajar con OneDrive.
    """
    if not TENANT_ID or not CLIENT_ID or not CLIENT_SECRET:
        logger.error("Configuración de OneDrive incompleta")
        raise HTTPException(
            status_code=500,
            detail="Configuración de OneDrive incompleta",
        )

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.post(
                TOKEN_URL,
                data={
                    "grant_type": "client_credentials",
                    "client_id": CLIENT_ID,
                    "client_secret": CLIENT_SECRET,
                    "scope": "https://graph.microsoft.com/.default",
                },
            )

            logger.info(f"Token OneDrive obtenido: {response.status_code}")

            if response.status_code != 200:
                logger.error(f"Error token: {response.text}")
                raise HTTPException(
                    status_code=500,
                    detail="No fue posible obtener token de OneDrive",
                )

            return response.json()["access_token"]

    except Exception as e:
        logger.error(f"Error al obtener token: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error al obtener token de OneDrive",
        )


# ============================================================
# CREAR / OBTENER CARPETA ONEDRIVE
# ============================================================

async def GES_Firmas_Ensure_Folder(
    client: httpx.AsyncClient,
    headers: dict,
    folder_path: str,
) -> str:
    """
    Busca cada carpeta de la ruta y la crea si no existe.
    """
    parts = folder_path.strip("/").split("/")
    current_path = ""
    folder_id = "root"

    for part in parts:
        current_path = f"{current_path}/{part}" if current_path else part
        url = f"{GRAPH_URL}/users/{USER_EMAIL}/drive/root:/{current_path}"

        try:
            response = await client.get(url, headers=headers)
            logger.info(f"Check folder '{current_path}': {response.status_code}")

            if response.status_code == 200:
                folder_id = response.json()["id"]

            elif response.status_code == 404:
                path_parts = current_path.split("/")
                parent_path = "/".join(path_parts[:-1])

                if not parent_path:
                    create_url = f"{GRAPH_URL}/users/{USER_EMAIL}/drive/root/children"
                else:
                    create_url = (
                        f"{GRAPH_URL}/users/{USER_EMAIL}"
                        f"/drive/root:/{parent_path}:/children"
                    )

                create_response = await client.post(
                    create_url,
                    headers={**headers, "Content-Type": "application/json"},
                    json={
                        "name": part,
                        "folder": {},
                        "@microsoft.graph.conflictBehavior": "rename",
                    },
                )

                logger.info(f"Create folder '{part}': {create_response.status_code}")

                if create_response.status_code not in (200, 201):
                    logger.error(f"Error creando carpeta: {create_response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"No fue posible crear carpeta {part} en OneDrive",
                    )

                folder_id = create_response.json()["id"]

            else:
                logger.error(f"Error consultando carpeta: {response.text}")
                raise HTTPException(
                    status_code=500,
                    detail="Error accediendo a OneDrive",
                )

        except Exception as e:
            logger.error(f"Error al acceder a carpeta: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error al acceder a OneDrive",
            )

    return folder_id


# ============================================================
# DECODIFICAR FIRMA BASE64 (dataURL → bytes + extensión)
# ============================================================

def GES_Firmas_Decodificar_Base64(data_url: str) -> Tuple[bytes, str]:
    """
    Convierte un dataURL tipo:
        data:image/png;base64,iVBORw0KGgoAAAANSUhEUg...
    en (bytes, extensión).
    """
    if not data_url or not isinstance(data_url, str):
        raise HTTPException(400, "La firma está vacía o no es válida")

    match = re.match(
        r"^data:image/(png|jpe?g|webp);base64,(.+)$",
        data_url,
        flags=re.IGNORECASE | re.DOTALL,
    )

    if not match:
        raise HTTPException(
            400,
            "Formato de firma inválido (se esperaba dataURL base64 de imagen)",
        )

    ext = match.group(1).lower()
    if ext == "jpeg":
        ext = "jpg"

    try:
        content = base64.b64decode(match.group(2))
    except Exception:
        raise HTTPException(400, "No se pudo decodificar la firma")

    if not content:
        raise HTTPException(400, "La firma decodificada está vacía")

    if len(content) > MAX_FILE_SIZE:
        max_mb = MAX_FILE_SIZE // (1024 * 1024)
        raise HTTPException(
            400,
            f"La firma excede el tamaño máximo de {max_mb} MB",
        )

    return content, ext


# ============================================================
# SUBIR FIRMAS A ONEDRIVE
# ============================================================

async def GES_Firmas_Subir(
    patente: str,
    firmas: List[dict],
) -> List[dict]:
    """
    Sube las firmas a OneDrive bajo:
        Registros/{PATENTE}/{FECHA}-FIRMAS/

    firmas = [
      { "documento_id": 1, "firma_base64": "data:image/png;base64,..." },
      ...
    ]

    Devuelve la lista con los datos de OneDrive para persistir en BD.
    """
    if not firmas:
        return []

    token = await GES_Firmas_Get_Token()
    headers = {"Authorization": f"Bearer {token}"}

    patente = patente.upper().strip()
    fecha_str = datetime.now().strftime("%Y-%m-%d")
    folder_path = f"{ONEDRIVE_ROOT}/{patente}/{fecha_str}-FIRMAS"

    resultados: List[dict] = []

    async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT) as client:
        folder_id = await GES_Firmas_Ensure_Folder(
            client,
            headers,
            folder_path,
        )

        logger.info(f"Carpeta OneDrive firmas: {folder_path}")

        for item in firmas:
            doc_id = int(item.get("documento_id"))
            data_url = item.get("firma_base64")

            content, ext = GES_Firmas_Decodificar_Base64(data_url)

            filename = f"firma_doc_{doc_id}.{ext}"
            content_type = {
                "png": "image/png",
                "jpg": "image/jpeg",
                "webp": "image/webp",
            }.get(ext, "image/png")

            upload_url = (
                f"{GRAPH_URL}/users/{USER_EMAIL}"
                f"/drive/items/{folder_id}:/{filename}:/content"
            )

            try:
                response = await client.put(
                    upload_url,
                    headers={**headers, "Content-Type": content_type},
                    content=content,
                )

                logger.info(f"Upload firma doc {doc_id}: {response.status_code}")

                if response.status_code not in (200, 201):
                    logger.error(
                        f"Error subiendo firma doc {doc_id}: {response.text}"
                    )
                    raise HTTPException(
                        status_code=500,
                        detail=f"No fue posible subir la firma del documento {doc_id}",
                    )

                data = response.json()

                resultados.append({
                    "documento_id": doc_id,
                    "item_id": data.get("id", ""),
                    "filename": filename,
                    "path": f"{folder_path}/{filename}",
                    "web_url": data.get("webUrl", ""),
                })

            except HTTPException:
                raise
            except Exception as e:
                logger.error(f"Error al subir firma doc {doc_id}: {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error al subir la firma del documento {doc_id}",
                )

    logger.info(f"{len(resultados)} firma(s) subidas a OneDrive")
    return resultados


# ============================================================
# REGISTRAR FIRMAS EN BD (SP)
# ============================================================

def GES_Firmas_Registrar_DB(
    id_contrato: int,
    patente: str,
    firmas: List[dict],
    ip: Optional[str] = None,
    user_agent: Optional[str] = None,
):
    """
    Ejecuta: SP_GES_FIRMAS_GUARDAR
    """
    connection = None
    cursor = None

    try:
        connection = GES_Firmas_Conexion_DB()
        cursor = connection.cursor(dictionary=True)

        payload = {
            "id_contrato": id_contrato,
            "patente": patente.upper().strip(),
            "ip": ip,
            "user_agent": user_agent,
            "firmas": firmas,
        }

        json_data = json.dumps(payload, ensure_ascii=False)
        logger.info("Ejecutando SP_GES_FIRMAS_GUARDAR...")

        cursor.callproc("SP_GES_FIRMAS_GUARDAR", [json_data])

        resultado_sp = None
        for result in cursor.stored_results():
            filas = result.fetchall()
            if filas:
                resultado_sp = filas[0]
                break

        connection.commit()

        if not resultado_sp:
            logger.error("El procedimiento no retornó información")
            raise HTTPException(
                status_code=500,
                detail="El procedimiento no retornó información",
            )

        logger.info("SP_GES_FIRMAS_GUARDAR ejecutado correctamente")
        return resultado_sp

    except HTTPException:
        raise
    except Error as e:
        if connection:
            connection.rollback()

        # Error de negocio lanzado con SIGNAL SQLSTATE '45000'
        if e.errno == 1644:
            logger.warning(f"Error de negocio: {e.msg}")
            raise HTTPException(
                status_code=400,
                detail=str(e.msg),
            )

        logger.error(f"Error MySQL/SP: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en base de datos: {str(e)}",
        )

    except Exception as e:
        if connection:
            connection.rollback()
        logger.error(f"Error inesperado: {e}")
        raise HTTPException(
            status_code=500,
            detail="Error registrando las firmas",
        )

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.info("Conexión MySQL cerrada")


# ============================================================
# LISTAR FIRMAS DE UN CONTRATO (SP)
# ============================================================

def GES_Firmas_Listar_DB(id_contrato: int) -> List[dict]:
    """
    Ejecuta: SP_GES_FIRMAS_LISTAR_CONTRATO
    """
    connection = None
    cursor = None

    try:
        connection = GES_Firmas_Conexion_DB()
        cursor = connection.cursor(dictionary=True)

        cursor.callproc("SP_GES_FIRMAS_LISTAR_CONTRATO", (id_contrato,))

        firmas = []
        for result in cursor.stored_results():
            firmas = result.fetchall()
            break

        # Parsear firma_json (MySQL lo entrega como string)
        for f in firmas:
            if isinstance(f.get("FIRMA_JSON"), str):
                try:
                    f["FIRMA_JSON"] = json.loads(f["FIRMA_JSON"])
                except json.JSONDecodeError:
                    f["FIRMA_JSON"] = {}
            if isinstance(f.get("FIRMADO_EN"), datetime):
                f["FIRMADO_EN"] = f["FIRMADO_EN"].isoformat()

        return firmas

    except HTTPException:
        raise
    except Error as e:
        if e.errno == 1644:
            raise HTTPException(status_code=400, detail=str(e.msg))
        logger.error(f"Error MySQL listando firmas: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en base de datos: {str(e)}",
        )

    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.info("Conexión MySQL cerrada")


# ============================================================
# ENDPOINT: GUARDAR FIRMAS
# ============================================================

@router.post("/guardar")
async def GES_Firmas_Guardar(
    request: Request,
    body: dict = Body(...),
):
    """
    Body esperado:
    {
      "id_contrato": 1,
      "patente": "ABCD12",
      "firmas": [
        { "documento_id": 1, "firma_base64": "data:image/png;base64,..." },
        { "documento_id": 2, "firma_base64": "data:image/png;base64,..." }
      ]
    }
    """
    logger.info("Iniciando guardado de firmas")

    id_contrato = body.get("id_contrato")
    patente = body.get("patente")
    firmas = body.get("firmas")

    # ---------- Validaciones ----------
    if not id_contrato:
        raise HTTPException(400, "id_contrato es obligatorio")

    if not patente:
        raise HTTPException(400, "patente es obligatoria")

    if not isinstance(firmas, list) or not firmas:
        raise HTTPException(400, "Debe enviar al menos una firma")

    for f in firmas:
        if not f.get("documento_id"):
            raise HTTPException(400, "Cada firma debe tener documento_id")
        if not f.get("firma_base64"):
            raise HTTPException(
                400,
                f"Falta firma_base64 para documento {f.get('documento_id')}",
            )

    # Metadata de auditoría
    ip = request.client.host if request.client else None
    user_agent = request.headers.get("user-agent")

    # ---------- Subir a OneDrive ----------
    try:
        firmas_subidas = await GES_Firmas_Subir(
            patente=patente,
            firmas=firmas,
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error subiendo firmas: {e}")
        raise HTTPException(500, "Error al subir las firmas a OneDrive")

    # ---------- Registrar en BD (SP) ----------
    try:
        resultado_sp = GES_Firmas_Registrar_DB(
            id_contrato=int(id_contrato),
            patente=patente,
            firmas=firmas_subidas,
            ip=ip,
            user_agent=user_agent,
        )
    except HTTPException:
        # Rollback OneDrive si falla la BD
        logger.info("Rollback de firmas en OneDrive por error en BD")
        try:
            token = await GES_Firmas_Get_Token()
            headers = {"Authorization": f"Bearer {token}"}
            async with httpx.AsyncClient(timeout=30) as client:
                for f in firmas_subidas:
                    if f.get("item_id"):
                        delete_url = (
                            f"{GRAPH_URL}/users/{USER_EMAIL}"
                            f"/drive/items/{f['item_id']}"
                        )
                        await client.delete(delete_url, headers=headers)
        except Exception as rollback_error:
            logger.error(f"Error en rollback de firmas: {rollback_error}")
        raise

    # ---------- Respuesta ----------
    logger.info(f"Firmas registradas correctamente. Contrato: {id_contrato}")

    return {
        "estado": "OK",
        "mensaje": "Firmas guardadas correctamente",
        "data": {
            "id_contrato": id_contrato,
            "patente": patente.upper().strip(),
            "total": len(firmas_subidas),
            "resultado_sp": resultado_sp,
            "firmas": firmas_subidas,
        },
    }


# ============================================================
# ENDPOINT: LISTAR FIRMAS DE UN CONTRATO
# ============================================================

@router.get("/listar/{id_contrato}")
async def GES_Firmas_Listar(id_contrato: int):
    """
    Devuelve todas las firmas de un contrato.
    """
    logger.info(f"Listando firmas del contrato {id_contrato}")

    try:
        firmas = GES_Firmas_Listar_DB(id_contrato)

        return {
            "estado": "OK",
            "mensaje": "Firmas obtenidas correctamente",
            "data": {
                "id_contrato": id_contrato,
                "total": len(firmas),
                "firmas": firmas,
            },
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listando firmas: {e}")
        raise HTTPException(500, f"Error al listar las firmas: {str(e)}")


# ============================================================
# ENDPOINT: OBTENER FIRMA POR ITEM_ID (proxy OneDrive)
# ============================================================

@router.get("/firma/{item_id}")
async def GES_Firmas_Obtener_Firma(item_id: str):
    """
    Devuelve la imagen de la firma desde OneDrive haciendo de proxy.
    El item_id es el ID de Microsoft Graph del archivo.
    """
    logger.info(f"Obteniendo firma con item_id: {item_id}")

    if not item_id or len(item_id) > 200:
        raise HTTPException(400, "item_id inválido")

    try:
        token = await GES_Firmas_Get_Token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{GRAPH_URL}/users/{USER_EMAIL}/drive/items/{item_id}/content"

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.error(
                    f"Error obteniendo firma: {response.status_code} - {response.text}"
                )
                raise HTTPException(
                    status_code=response.status_code,
                    detail="No se pudo obtener la firma desde OneDrive",
                )

            content_type = response.headers.get("content-type", "image/png")

            return Response(
                content=response.content,
                media_type=content_type,
                headers={
                    "Cache-Control": "public, max-age=3600",
                },
            )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error inesperado obteniendo firma: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo la firma: {str(e)}",
        )


# ============================================================
# ENDPOINT: HEALTH CHECK
# ============================================================

@router.get("/health")
async def GES_Firmas_Health_Check():
    """
    Endpoint para verificar el estado del servicio.
    """
    try:
        connection = GES_Firmas_Conexion_DB()
        connection.close()

        one_drive_configured = all([
            TENANT_ID, CLIENT_ID, CLIENT_SECRET, USER_EMAIL
        ])

        return {
            "estado": "OK",
            "mysql": "conectado",
            "onedrive": "configurado" if one_drive_configured else "no configurado",
            "timestamp": datetime.now().isoformat(),
        }

    except Exception as e:
        logger.error(f"Health check falló: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Health check falló: {str(e)}",
        )