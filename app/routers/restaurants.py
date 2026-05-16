"""
routers/restaurants.py
----------------------
Full CRUD endpoints for the restaurants table.
"""

from fastapi import APIRouter, Depends, HTTPException
import MySQLdb

from app.db.connection import get_db, get_cursor
from app.models.schemas import RestaurantCreate, RestaurantUpdate, RestaurantResponse

router = APIRouter(prefix="/restaurants", tags=["Restaurants"])


@router.get("/", response_model=list[RestaurantResponse])
def list_restaurants(
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: MySQLdb.Connection = Depends(get_db),
):
    """List all restaurants with optional status filter."""
    sql = "SELECT * FROM restaurants WHERE 1=1"
    params = []
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_cursor(db) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/{restaurant_id}", response_model=RestaurantResponse)
def get_restaurant(restaurant_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get a single restaurant by ID."""
    with get_cursor(db) as cur:
        cur.execute("SELECT * FROM restaurants WHERE id = %s", (restaurant_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Restaurant not found")
    return row


@router.get("/{restaurant_id}/items")
def get_restaurant_items(restaurant_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get all menu items for a restaurant."""
    with get_cursor(db) as cur:
        cur.execute(
            "SELECT * FROM items WHERE restaurant_id = %s AND is_available = 1",
            (restaurant_id,)
        )
        return cur.fetchall()


@router.post("/", response_model=RestaurantResponse, status_code=201)
def create_restaurant(
    payload: RestaurantCreate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """Create a new restaurant."""
    sql = """
        INSERT INTO restaurants (address_id, name, mobile_number, status)
        VALUES (%s, %s, %s, %s)
    """
    with get_cursor(db) as cur:
        cur.execute(sql, (
            payload.address_id, payload.name,
            payload.mobile_number, payload.status,
        ))
        new_id = cur.lastrowid
        cur.execute("SELECT * FROM restaurants WHERE id = %s", (new_id,))
        return cur.fetchone()


@router.put("/{restaurant_id}", response_model=RestaurantResponse)
def update_restaurant(
    restaurant_id: int,
    payload: RestaurantUpdate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """Partially update a restaurant."""
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{col} = %s" for col in updates)
    sql = f"UPDATE restaurants SET {set_clause} WHERE id = %s"

    with get_cursor(db) as cur:
        cur.execute(sql, (*updates.values(), restaurant_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Restaurant not found")
        cur.execute("SELECT * FROM restaurants WHERE id = %s", (restaurant_id,))
        return cur.fetchone()


@router.delete("/{restaurant_id}", status_code=204)
def delete_restaurant(restaurant_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Soft delete — sets status to inactive."""
    with get_cursor(db) as cur:
        cur.execute(
            "UPDATE restaurants SET status = 'inactive' WHERE id = %s", (restaurant_id,)
        )
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Restaurant not found")