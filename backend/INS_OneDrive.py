# INS_OneDrive.py
import os
import httpx
from datetime import datetime, timezone

TENANT_ID     = os.environ.get("TENANT_ID",     "10680579-5ab7-45dc-bfe7-7df399b8a082")
CLIENT_ID     = os.environ.get("CLIENT_ID",     "19351c6c-1058-40d1-a601-82732c4afa8f")
CLIENT_SECRET = os.environ.get("CLIENT_SECRET", ".4d8Q~sWvkDVQUlr76vkkrBfBEUKtHX5Oect_bTu")
USER_EMAIL    = os.environ.get("USER_EMAIL",    "no-reply@ecotranschile.cl")

ONEDRIVE_ROOT = "Inspecciones"
TOKEN_URL = f"https://login.microsoftonline.com/{TENANT_ID}/oauth2/v2.0/token"
GRAPH_URL = "https://graph.microsoft.com/v1.0"


async def get_token() -> str:
    async with httpx.AsyncClient() as client:
        r = await client.post(
            TOKEN_URL,
            data={
                "grant_type":    "client_credentials",
                "client_id":     CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "scope":         "https://graph.microsoft.com/.default",
            },
        )
        print(f"[OneDrive] Token: {r.status_code}")
        r.raise_for_status()
        return r.json()["access_token"]


async def _ensure_folder(client: httpx.AsyncClient, headers: dict, folder_path: str) -> str:
    parts = folder_path.strip("/").split("/")
    current_path = ""
    folder_id = "root"

    for part in parts:
        current_path = f"{current_path}/{part}" if current_path else part
        url = f"{GRAPH_URL}/users/{USER_EMAIL}/drive/root:/{current_path}"
        r = await client.get(url, headers=headers)
        print(f"[OneDrive] Check folder '{current_path}': {r.status_code}")

        if r.status_code == 200:
            folder_id = r.json()["id"]
        elif r.status_code == 404:
            parent_path = "/".join(current_path.split("/")[:-1])
            create_url = (
                f"{GRAPH_URL}/users/{USER_EMAIL}/drive/root/children"
                if not parent_path
                else f"{GRAPH_URL}/users/{USER_EMAIL}/drive/root:/{parent_path}:/children"
            )
            r = await client.post(
                create_url,
                headers={**headers, "Content-Type": "application/json"},
                json={"name": part, "folder": {}, "@microsoft.graph.conflictBehavior": "rename"},
            )
            print(f"[OneDrive] Create '{part}': {r.status_code}")
            r.raise_for_status()
            folder_id = r.json()["id"]
        else:
            r.raise_for_status()

    return folder_id


async def upload_photos_to_onedrive(
    registration: str,
    files: list[tuple[str, bytes]],
) -> list[dict]:
    """
    Sube fotos y retorna lista de objetos:
      { item_id, filename, path }
    Las imágenes se sirven via /inspecciones/foto/{item_id} (proxy autenticado).
    """
    if not files:
        return []

    token    = await get_token()
    headers  = {"Authorization": f"Bearer {token}"}
    date_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    folder_path = f"{ONEDRIVE_ROOT}/{registration.upper()}/{date_str}"
    result: list[dict] = []

    async with httpx.AsyncClient(timeout=60) as client:
        folder_id = await _ensure_folder(client, headers, folder_path)
        print(f"[OneDrive] Carpeta: {folder_id}")

        for filename, content in files:
            put_url = (
                f"{GRAPH_URL}/users/{USER_EMAIL}/drive/items/{folder_id}:/"
                f"{filename}:/content"
            )
            r = await client.put(
                put_url,
                headers={**headers, "Content-Type": "image/jpeg"},
                content=content,
            )
            print(f"[OneDrive] Upload '{filename}': {r.status_code}")
            r.raise_for_status()

            item_id = r.json().get("id", "")
            result.append({
                "item_id":  item_id,
                "filename": filename,
                "path":     f"{folder_path}/{filename}",
            })

    print(f"[OneDrive] {len(result)} foto(s) subidas")
    return result


async def get_photo_content(item_id: str) -> tuple[bytes, str]:
    """
    Descarga el contenido de una foto dado su item_id.
    Retorna (bytes, content_type).
    Usado por el proxy endpoint /inspecciones/foto/{item_id}.
    """
    token = await get_token()
    headers = {"Authorization": f"Bearer {token}"}

    async with httpx.AsyncClient(timeout=30) as client:
        r = await client.get(
            f"{GRAPH_URL}/users/{USER_EMAIL}/drive/items/{item_id}/content",
            headers=headers,
            follow_redirects=True,
        )
        r.raise_for_status()
        content_type = r.headers.get("content-type", "image/jpeg")
        return r.content, content_type