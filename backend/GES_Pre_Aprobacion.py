import os
import json
import httpx
import logging

from datetime import datetime
from typing import Optional, List, Tuple

from fastapi import (
    APIRouter,
    UploadFile,
    File,
    Form,
    HTTPException,
    Response,
)


import mysql.connector
from mysql.connector import Error

# ============================================================
# CONFIGURACIÓN DE LOGGING
# ============================================================

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("GES - Pre_Aprobacion")

# ============================================================
# ROUTER
# ============================================================

router = APIRouter(
    prefix="/GES_Pre_Aprobacion",
    tags=["GES - Pre_Aprobacion"]
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

# Carpeta oficial
ONEDRIVE_ROOT = "Registros"
MAX_FILE_SIZE = 10 * 1024 * 1024  # 10 MB
UPLOAD_TIMEOUT = 120

TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_URL = "https://graph.microsoft.com/v1.0"

# ============================================================
# CONEXIÓN MYSQL
# ============================================================
def GES_Pre_Aprobacion_Conexion_DB():
    """
    Crea una conexión a MySQL usando socket de Cloud SQL.
    """
    try:
        # Usando las variables definidas al inicio
        connection = mysql.connector.connect(
            user=DB_USER,
            password=DB_PASS,
            database=DB_NAME,
            unix_socket=DB_SOCKET,  # Conexión mediante socket Unix
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
async def GES_Pre_Aprobacion_Get_Token() -> str:
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
async def GES_Pre_Aprobacion_Ensure_Folder(
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
                    create_url = f"{GRAPH_URL}/users/{USER_EMAIL}/drive/root:/{parent_path}:/children"

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
# SUBIR FOTOGRAFÍAS A ONEDRIVE
# ============================================================
async def GES_Pre_Aprobacion_Subir_Fotos(
    patente: str,
    fecha_ingreso: datetime,
    archivos: List[Tuple[str, bytes]],
) -> List[dict]:
    """
    Sube las fotografías de la pre-aprobación.
    """
    if not archivos:
        return []

    token = await GES_Pre_Aprobacion_Get_Token()
    headers = {"Authorization": f"Bearer {token}"}
    patente = patente.upper().strip()
    fecha_str = fecha_ingreso.strftime("%Y-%m-%d")
    folder_path = f"{ONEDRIVE_ROOT}/{patente}/{fecha_str}-PRE-APROBACION"
    resultados = []

    async with httpx.AsyncClient(timeout=UPLOAD_TIMEOUT) as client:
        folder_id = await GES_Pre_Aprobacion_Ensure_Folder(
            client,
            headers,
            folder_path,
        )

        logger.info(f"Carpeta OneDrive: {folder_path}")

        for filename, content in archivos:
            filename = filename.replace("/", "_").replace("\\", "_")
            
            if len(content) > MAX_FILE_SIZE:
                logger.error(f"Archivo {filename} excede el tamaño máximo")
                raise HTTPException(
                    status_code=400,
                    detail=f"La fotografía {filename} excede el tamaño máximo de 10 MB",
                )

            upload_url = f"{GRAPH_URL}/users/{USER_EMAIL}/drive/items/{folder_id}:/{filename}:/content"

            try:
                response = await client.put(
                    upload_url,
                    headers={**headers, "Content-Type": "image/jpeg"},
                    content=content,
                )

                logger.info(f"Upload '{filename}': {response.status_code}")

                if response.status_code not in (200, 201):
                    logger.error(f"Error subiendo '{filename}': {response.text}")
                    raise HTTPException(
                        status_code=500,
                        detail=f"No fue posible subir la fotografía {filename}",
                    )

                data = response.json()
                item_id = data.get("id", "")
                resultados.append({
                    "item_id": item_id,
                    "filename": filename,
                    "path": f"{folder_path}/{filename}",
                })

            except Exception as e:
                logger.error(f"Error al subir '{filename}': {e}")
                raise HTTPException(
                    status_code=500,
                    detail=f"Error al subir la fotografía {filename}",
                )

    logger.info(f"{len(resultados)} fotografía(s) subidas")
    return resultados

# ============================================================
# PREPARAR FOTOGRAFÍAS
# ============================================================
async def GES_Pre_Aprobacion_Preparar_Fotos(
    patente: str,
    fecha_ingreso: datetime,
    frente: Optional[UploadFile],
    lado_izquierdo: Optional[UploadFile],
    atras: Optional[UploadFile],
    lado_derecho: Optional[UploadFile],
) -> List[dict]:
    """
    Lee las cuatro fotografías y las prepara para OneDrive.
    """
    archivos = []
    fotografias = [
        ("frente", frente),
        ("lado_izquierdo", lado_izquierdo),
        ("atras", atras),
        ("lado_derecho", lado_derecho),
    ]

    for nombre, archivo in fotografias:
        if archivo is None:
            logger.error(f"Fotografía {nombre} es obligatoria")
            raise HTTPException(
                status_code=400,
                detail=f"La fotografía {nombre} es obligatoria",
            )

        if archivo.content_type not in (
            "image/jpeg",
            "image/jpg",
            "image/png",
            "image/webp",
        ):
            logger.error(f"Tipo de archivo no válido para {nombre}: {archivo.content_type}")
            raise HTTPException(
                status_code=400,
                detail=f"La fotografía {nombre} debe ser una imagen",
            )

        try:
            contenido = await archivo.read()
            
            if not contenido:
                logger.error(f"Fotografía {nombre} está vacía")
                raise HTTPException(
                    status_code=400,
                    detail=f"La fotografía {nombre} está vacía",
                )

            if len(contenido) > MAX_FILE_SIZE:
                logger.error(f"Fotografía {nombre} excede el tamaño máximo")
                raise HTTPException(
                    status_code=400,
                    detail=f"La fotografía {nombre} excede el tamaño máximo de 10 MB",
                )

            extension = ".jpg"
            if archivo.filename:
                filename_lower = archivo.filename.lower()
                if filename_lower.endswith(".png"):
                    extension = ".png"
                elif filename_lower.endswith(".webp"):
                    extension = ".webp"

            filename = f"{patente.upper()}_{nombre}{extension}"
            archivos.append((filename, contenido))

        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error procesando fotografía {nombre}: {e}")
            raise HTTPException(
                status_code=500,
                detail=f"Error procesando la fotografía {nombre}",
            )

    return await GES_Pre_Aprobacion_Subir_Fotos(
        patente=patente,
        fecha_ingreso=fecha_ingreso,
        archivos=archivos,
    )

# ============================================================
# EJECUTAR STORED PROCEDURE
# ============================================================
def GES_Pre_Aprobacion_Registrar(
    usuario_id: int,
    patente: str,
    fecha_hora: datetime,
    resultado: str,
    observacion: Optional[str],
    fotografias: List[dict],
):
    """
    Ejecuta: SP_GES_PREAPROBACION_VEHICULO
    """
    connection = None
    cursor = None

    try:
        connection = GES_Pre_Aprobacion_Conexion_DB()
        cursor = connection.cursor(dictionary=True)

        payload = {
            "usuario_id": usuario_id,
            "patente": patente.upper().strip(),
            "fecha_hora": fecha_hora.strftime("%Y-%m-%dT%H:%M:%S"),
            "resultado": resultado.upper().strip(),
            "observacion": observacion,
            "fotografias": fotografias,
        }

        json_data = json.dumps(payload, ensure_ascii=False)
        logger.info("Ejecutando SP...")

        cursor.callproc("SP_GES_PREAPROBACION_VEHICULO", [json_data])

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

        logger.info("SP ejecutado correctamente")
        return resultado_sp

    except HTTPException:
        raise
    except Error as e:
        if connection:
            connection.rollback()
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
            detail="Error procesando la pre-aprobación",
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.info("Conexión MySQL cerrada")

# ============================================================
# ENDPOINT PRINCIPAL
# ============================================================
@router.post("/")
async def GES_Pre_Aprobacion_Procesar(
    usuario_id: int = Form(...),
    patente: str = Form(...),
    fecha_hora: str = Form(...),
    resultado: str = Form(...),
    observacion: Optional[str] = Form(None),
    frente: Optional[UploadFile] = File(None),
    lado_izquierdo: Optional[UploadFile] = File(None),
    atras: Optional[UploadFile] = File(None),
    lado_derecho: Optional[UploadFile] = File(None),
):
    """
    Endpoint principal para registrar una pre-aprobación de vehículo.
    """
    logger.info(f"Iniciando procesamiento de pre-aprobación para patente: {patente}")

    # Normalizar datos
    patente = patente.upper().strip()
    resultado = resultado.upper().strip()

    # Validar patente
    if not patente:
        logger.error("Patente vacía")
        raise HTTPException(
            status_code=400,
            detail="La patente es obligatoria",
        )

    # Validar resultado
    resultados_validos = ["PENDIENTE", "APROBADO", "OBSERVADO", "RECHAZADO", "NO CALIFICA", "EN PROCESO"]
    if resultado not in resultados_validos:
        logger.error(f"Resultado no válido: {resultado}")
        raise HTTPException(
            status_code=400,
            detail="Resultado no válido. Valores permitidos: PENDIENTE, APROBADO, OBSERVADO, RECHAZADO, NO CALIFICA, EN PROCESO",
        )

    # Observación
    if observacion:
        observacion = observacion.strip()

    # Fecha
    try:
        fecha_datetime = datetime.fromisoformat(fecha_hora)
    except ValueError:
        logger.error(f"Formato de fecha inválido: {fecha_hora}")
        raise HTTPException(
            status_code=400,
            detail="La fecha_hora no tiene un formato válido. Use YYYY-MM-DDTHH:MM:SS",
        )

    # Fotografías (solo para APROBADO)
    fotografias = []
    if resultado == "APROBADO":
        logger.info("Preparando fotografías para aprobación")
        try:
            fotografias = await GES_Pre_Aprobacion_Preparar_Fotos(
                patente=patente,
                fecha_ingreso=fecha_datetime,
                frente=frente,
                lado_izquierdo=lado_izquierdo,
                atras=atras,
                lado_derecho=lado_derecho,
            )
        except HTTPException:
            raise
        except Exception as e:
            logger.error(f"Error preparando fotografías: {e}")
            raise HTTPException(
                status_code=500,
                detail="Error al preparar las fotografías",
            )

    # Registrar en base de datos
    try:
        resultado_sp = GES_Pre_Aprobacion_Registrar(
            usuario_id=usuario_id,
            patente=patente,
            fecha_hora=fecha_datetime,
            resultado=resultado,
            observacion=observacion,
            fotografias=fotografias,
        )
    except HTTPException:
        # Si falla la BD, hacer rollback de fotos
        if fotografias:
            logger.info("Rollback de fotografías por error en BD")
            try:
                token = await GES_Pre_Aprobacion_Get_Token()
                headers = {"Authorization": f"Bearer {token}"}
                async with httpx.AsyncClient(timeout=30) as client:
                    for foto in fotografias:
                        item_id = foto.get("item_id")
                        if item_id:
                            delete_url = f"{GRAPH_URL}/users/{USER_EMAIL}/drive/items/{item_id}"
                            await client.delete(delete_url, headers=headers)
            except Exception as rollback_error:
                logger.error(f"Error en rollback de fotos: {rollback_error}")
        raise

    # Respuesta
    logger.info(f"Pre-aprobación registrada correctamente para patente: {patente}")
    return {
        "estado": "OK",
        "mensaje": "Pre-aprobación registrada correctamente",
        "data": resultado_sp,
        "fotografias": fotografias,
    }

# ============================================================
# LISTAR REGISTROS DE PRE-APROBACIÓN
# ============================================================
@router.get("/listar")
async def GES_Pre_Aprobacion_Listar():
    logger.info("Listando todos los registros de pre-aprobación")

    connection = None
    cursor = None

    try:
        # -------- Conexión --------
        connection = GES_Pre_Aprobacion_Conexion_DB()
        cursor = connection.cursor(dictionary=True)

        # -------- SELECT --------
        query = """
            SELECT
                id,
                patente,
                fecha_hora,
                resultado,
                creado_por,
                creado_por_nombre,
                contrato_id
            FROM VW_GES_PRE_APROBACION
        """
        logger.info(f"Ejecutando consulta: {query}")
        cursor.execute(query)
        registros = cursor.fetchall()

        # -------- Formatear fechas --------
        for registro in registros:
            for campo in ["fecha_hora", "created_at"]:
                valor = registro.get(campo)
                if valor and isinstance(valor, datetime):
                    registro[campo] = valor.isoformat()

        return {
            "estado": "OK",
            "mensaje": "Registros obtenidos correctamente",
            "data": {
                "registros": registros,
                "total": len(registros),
            },
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Error as e:
        logger.error(f"Error MySQL al listar registros: {e}")
        raise HTTPException(500, f"Error en base de datos: {str(e)}")
    except Exception as e:
        logger.error(f"Error inesperado al listar registros: {e}")
        raise HTTPException(500, f"Error al listar los registros: {str(e)}")
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.info("Conexión MySQL cerrada")

# ============================================================
# OBTENER REGISTRO POR ID
# ============================================================
@router.get("/{registro_id}")
async def GES_Pre_Aprobacion_Obtener(
    registro_id: int,
):
    """
    Endpoint para obtener un registro específico de pre-aprobación por su ID.
    """
    logger.info(f"Obteniendo registro de pre-aprobación con ID: {registro_id}")

    connection = None
    cursor = None

    try:
        connection = GES_Pre_Aprobacion_Conexion_DB()
        cursor = connection.cursor(dictionary=True)

        # llamar al SP
        cursor.callproc("SP_GES_PREAPROBACION_BUSCAR_ID", (registro_id,))

        registro = None

        # recorremos lo obtenido
        for result in cursor.stored_results():
            registro = result.fetchone()
            break
            
        # si no encuentra info
        if not registro:
            raise HTTPException(
                status_code=404,
                detail=f"No se encontró el registro con ID {registro_id}",
            )

        # Parsear fotografías
        if registro.get("fotografias"):
            if isinstance(registro["fotografias"], str):
                try:
                    registro["fotografias"] = json.loads(registro["fotografias"])
                except json.JSONDecodeError:
                    registro["fotografias"] = []
        else:
            registro["fotografias"] = []

        # Formatear fechas
        for campo in ["fecha_hora", "created_at", "updated_at"]:
            if registro.get(campo) and isinstance(registro[campo], datetime):
                registro[campo] = registro[campo].isoformat()

        logger.info(f"Registro {registro_id} obtenido correctamente")

        return {
            "estado": "OK",
            "mensaje": "Registro obtenido correctamente",
            "data": registro,
            "timestamp": datetime.now().isoformat(),
        }

    except HTTPException:
        raise
    except Error as e:
        logger.error(f"Error MySQL al obtener registro: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error en base de datos: {str(e)}",
        )
    except Exception as e:
        logger.error(f"Error inesperado al obtener registro: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error al obtener el registro: {str(e)}",
        )
    finally:
        if cursor:
            cursor.close()
        if connection and connection.is_connected():
            connection.close()
            logger.info("Conexión MySQL cerrada")

# ============================================================
# OBTENER FOTO POR ID
# ============================================================
@router.get("/foto/{item_id}")
async def GES_Pre_Aprobacion_Obtener_Foto(item_id: str):
    """
    Devuelve la imagen desde OneDrive haciendo de proxy.
    El item_id es el ID de Microsoft Graph del archivo.
    """
    logger.info(f"Obteniendo foto con item_id: {item_id}")

    try:
        token = await GES_Pre_Aprobacion_Get_Token()
        headers = {"Authorization": f"Bearer {token}"}
        url = f"{GRAPH_URL}/users/{USER_EMAIL}/drive/items/{item_id}/content"

        async with httpx.AsyncClient(timeout=60, follow_redirects=True) as client:
            response = await client.get(url, headers=headers)

            if response.status_code != 200:
                logger.error(f"Error obteniendo foto: {response.status_code} - {response.text}")
                raise HTTPException(
                    status_code=response.status_code,
                    detail="No se pudo obtener la fotografía desde OneDrive",
                )

            content_type = response.headers.get("content-type", "image/jpeg")

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
        logger.error(f"Error inesperado obteniendo foto: {e}")
        raise HTTPException(
            status_code=500,
            detail=f"Error obteniendo la fotografía: {str(e)}",
        )
# ============================================================
# ENDPOINT DE HEALTH CHECK
# ============================================================

@router.get("/health")
async def GES_Pre_Aprobacion_Health_Check():
    """
    Endpoint para verificar el estado del servicio.
    """
    try:
        connection = GES_Pre_Aprobacion_Conexion_DB()
        connection.close()
        
        one_drive_configured = all([TENANT_ID, CLIENT_ID, CLIENT_SECRET, USER_EMAIL])
        
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