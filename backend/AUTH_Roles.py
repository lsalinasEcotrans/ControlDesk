# AUTH_Roles.py
from fastapi import APIRouter, HTTPException, Path
from pydantic import BaseModel, Field
from typing import List, Optional
import mysql.connector
from mysql.connector import Error
import os
import json
from Database import get_db_connection

router = APIRouter(prefix="/roles", tags=["AUTH - Roles"])

# ---------------------------
# Pydantic Models
# ---------------------------
class MenuItemModel(BaseModel):
    title: str
    url: str
    icon: Optional[str] = None
    external: Optional[bool] = False  # 👈 FIX CLAVE
    items: Optional[List['MenuItemModel']] = []

    class Config:
        from_attributes = True


MenuItemModel.update_forward_refs()

class RoleBase(BaseModel):
    name: str = Field(..., example="Ejemplo 1")
    json_menu: List[MenuItemModel] = Field(
        ...,
        example=[
            {
                "title": "Operaciones",
                "url": "#",
                "icon": "Handshake",
                "items": [
                    {"title": "Contratos", "url": "#"},
                    {"title": "Documentos", "url": "#"}
                ]
            },
            {
                "title": "Facturacion",
                "url": "#",
                "icon": "Handshake",
                "items": [{"title": "General1", "url": "#"}]
            }
        ]
    )

class RoleCreate(RoleBase):
    pass

class RoleUpdate(BaseModel):
    name: Optional[str] = None
    json_menu: Optional[List[MenuItemModel]] = None

# ---------------------------
# Endpoints
# ---------------------------

# 🔹 Endpoint estático primero: lista simplificada para selects
@router.get("/list")
def get_roles_list():
    """
    Devuelve solo id y name de todos los roles (para selects en el frontend)
    """
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor(dictionary=True)
    query = "SELECT id, name FROM AUTH_ROLES ORDER BY name ASC;"
    try:
        cursor.execute(query)
        roles = cursor.fetchall()
        return roles
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando query: {e}")
    finally:
        cursor.close()
        conn.close()

# 🔹 Obtener todos los roles completos
@router.get("")
def get_all_roles():
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor(dictionary=True)
    query = "SELECT id, name, json_menu, created_at FROM AUTH_ROLES ORDER BY id ASC;"
    try:
        cursor.execute(query)
        result = cursor.fetchall()
        for row in result:
            if isinstance(row["json_menu"], str):
                row["json_menu"] = json.loads(row["json_menu"])
        return result
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando query: {e}")
    finally:
        cursor.close()
        conn.close()

# 🔹 Obtener un rol por ID
@router.get("/id/{role_id}")
def get_role_by_id(role_id: int = Path(..., description="ID del rol")):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor(dictionary=True)
    query = "SELECT id, name, json_menu, created_at FROM AUTH_ROLES WHERE id = %s;"
    try:
        cursor.execute(query, (role_id,))
        result = cursor.fetchone()
        if not result:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        if isinstance(result["json_menu"], str):
            result["json_menu"] = json.loads(result["json_menu"])
        return result
    except Error as e:
        raise HTTPException(status_code=500, detail=f"Error ejecutando query: {e}")
    finally:
        cursor.close()
        conn.close()

# 🔹 Crear nuevo rol
@router.post("")
def create_role(role: RoleCreate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor()
    query = "INSERT INTO AUTH_ROLES (name, json_menu) VALUES (%s, %s);"
    try:
        json_data = json.dumps([item.dict() for item in role.json_menu])
        cursor.execute(query, (role.name, json_data))
        conn.commit()
        return {"message": "Rol creado exitosamente", "role_id": cursor.lastrowid}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error insertando rol: {e}")
    finally:
        cursor.close()
        conn.close()

# 🔹 Actualizar rol existente
@router.put("/{role_id}")
def update_role(role_id: int, role: RoleUpdate):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor()
    fields = []
    values = []

    if role.name:
        fields.append("name = %s")
        values.append(role.name)
    if role.json_menu:
        json_data = json.dumps([item.dict() for item in role.json_menu])
        fields.append("json_menu = %s")
        values.append(json_data)

    if not fields:
        raise HTTPException(status_code=400, detail="No hay campos para actualizar")

    query = f"UPDATE AUTH_ROLES SET {', '.join(fields)} WHERE id = %s"
    values.append(role_id)

    try:
        cursor.execute(query, tuple(values))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        return {"message": "Rol actualizado correctamente"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error actualizando rol: {e}")
    finally:
        cursor.close()
        conn.close()

# 🔹 Eliminar rol
@router.delete("/{role_id}")
def delete_role(role_id: int):
    conn = get_db_connection()
    if not conn:
        raise HTTPException(status_code=500, detail="No se pudo conectar a la base de datos")

    cursor = conn.cursor()
    query = "DELETE FROM AUTH_ROLES WHERE id = %s;"
    try:
        cursor.execute(query, (role_id,))
        conn.commit()
        if cursor.rowcount == 0:
            raise HTTPException(status_code=404, detail="Rol no encontrado")
        return {"message": "Rol eliminado correctamente"}
    except Error as e:
        conn.rollback()
        raise HTTPException(status_code=500, detail=f"Error eliminando rol: {e}")
    finally:
        cursor.close()
        conn.close()
