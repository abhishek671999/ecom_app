"""
routers/items.py
----------------
Full CRUD endpoints for the items (menu) table.
"""

from fastapi import APIRouter, Depends, HTTPException
import MySQLdb

from app.db.connection import get_db, get_cursor
from app.models.schemas import ItemCreate, ItemUpdate, ItemResponse

router = APIRouter(prefix="/items", tags=["Items"])


@router.get("/", response_model=list[ItemResponse])
def list_items(
    restaurant_id: int | None = None,
    is_available: bool | None = None,
    limit: int = 50,
    offset: int = 0,
    db: MySQLdb.Connection = Depends(get_db),
):
    """List items with optional filters by restaurant or availability."""
    sql = "SELECT * FROM items WHERE 1=1"
    params = []
    if restaurant_id is not None:
        sql += " AND restaurant_id = %s"
        params.append(restaurant_id)
    if is_available is not None:
        sql += " AND is_available = %s"
        params.append(int(is_available))
    sql += " ORDER BY name LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_cursor(db) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/{item_id}", response_model=ItemResponse)
def get_item(item_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get a single item by ID."""
    with get_cursor(db) as cur:
        cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Item not found")
    return row


@router.post("/", response_model=ItemResponse, status_code=201)
def create_item(payload: ItemCreate, db: MySQLdb.Connection = Depends(get_db)):
    """Create a new menu item."""
    sql = """
        INSERT INTO items (restaurant_id, name, price, is_available)
        VALUES (%s, %s, %s, %s)
    """
    try:
        with get_cursor(db) as cur:
            cur.execute(sql, (
                payload.restaurant_id, payload.name,
                payload.price, int(payload.is_available),
            ))
            new_id = cur.lastrowid
            cur.execute("SELECT * FROM items WHERE id = %s", (new_id,))
            return cur.fetchone()
    except MySQLdb.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Conflict: {e.args[1]}")


@router.put("/{item_id}", response_model=ItemResponse)
def update_item(
    item_id: int,
    payload: ItemUpdate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """Partially update a menu item (name, price, availability)."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    # Convert bool to int for MySQL
    if "is_available" in updates:
        updates["is_available"] = int(updates["is_available"])

    set_clause = ", ".join(f"{col} = %s" for col in updates)
    sql = f"UPDATE items SET {set_clause} WHERE id = %s"

    with get_cursor(db) as cur:
        cur.execute(sql, (*updates.values(), item_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found")
        cur.execute("SELECT * FROM items WHERE id = %s", (item_id,))
        return cur.fetchone()


@router.delete("/{item_id}", status_code=204)
def delete_item(item_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Mark item as unavailable (soft delete)."""
    with get_cursor(db) as cur:
        cur.execute(
            "UPDATE items SET is_available = 0 WHERE id = %s", (item_id,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Item not found")