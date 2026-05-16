"""
routers/orders.py
-----------------
Endpoints for orders, order_items, and order_events.

Key design decisions (from our schema discussion):
- Creating an order also inserts a 'created' event into order_events (append-only)
- Status updates write a new row to order_events — never update event rows
- order_items are append-only once the order is created
"""

from fastapi import APIRouter, Depends, HTTPException
import MySQLdb

from app.db.connection import get_db, get_cursor
from app.models.schemas import (
    OrderCreate, OrderUpdate, OrderResponse,
    OrderItemCreate, OrderItemResponse,
    OrderEventCreate, OrderEventResponse,
)

router = APIRouter(prefix="/orders", tags=["Orders"])


# ===========================================================================
# Orders
# ===========================================================================

@router.get("/", response_model=list[OrderResponse])
def list_orders(
    customer_id: int | None = None,
    restaurant_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
    offset: int = 0,
    db: MySQLdb.Connection = Depends(get_db),
):
    """List orders with optional filters."""
    sql = "SELECT * FROM orders WHERE 1=1"
    params = []
    if customer_id:
        sql += " AND customer_id = %s"
        params.append(customer_id)
    if restaurant_id:
        sql += " AND restaurant_id = %s"
        params.append(restaurant_id)
    if status:
        sql += " AND status = %s"
        params.append(status)
    sql += " ORDER BY created_at DESC LIMIT %s OFFSET %s"
    params.extend([limit, offset])

    with get_cursor(db) as cur:
        cur.execute(sql, params)
        return cur.fetchall()


@router.get("/{order_id}", response_model=OrderResponse)
def get_order(order_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get a single order by ID."""
    with get_cursor(db) as cur:
        cur.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        row = cur.fetchone()
    if not row:
        raise HTTPException(status_code=404, detail="Order not found")
    return row


@router.post("/", response_model=OrderResponse, status_code=201)
def create_order(payload: OrderCreate, db: MySQLdb.Connection = Depends(get_db)):
    """
    Create a new order.
    Automatically inserts a 'created' event into order_events.
    Both inserts run in the same transaction.
    """
    order_sql = """
        INSERT INTO orders
            (customer_id, restaurant_id, delivery_address_id, total_amount, status)
        VALUES (%s, %s, %s, %s, 'created')
    """
    event_sql = """
        INSERT INTO order_events (order_id, event_type, triggered_by)
        VALUES (%s, 'created', 'system')
    """
    try:
        with get_cursor(db) as cur:
            cur.execute(order_sql, (
                payload.customer_id, payload.restaurant_id,
                payload.delivery_address_id, payload.total_amount,
            ))
            new_order_id = cur.lastrowid

            # Append first event — created
            cur.execute(event_sql, (new_order_id,))

            cur.execute("SELECT * FROM orders WHERE order_id = %s", (new_order_id,))
            return cur.fetchone()
    except MySQLdb.IntegrityError as e:
        raise HTTPException(status_code=409, detail=f"Conflict: {e.args[1]}")


@router.put("/{order_id}", response_model=OrderResponse)
def update_order(
    order_id: int,
    payload: OrderUpdate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """
    Update order status or assign a delivery partner.
    Status change automatically appends a new row to order_events.
    """
    updates = {k: v for k, v in payload.model_dump().items() if v is not None}
    if not updates:
        raise HTTPException(status_code=400, detail="No fields to update")

    set_clause = ", ".join(f"{col} = %s" for col in updates)
    sql = f"UPDATE orders SET {set_clause} WHERE order_id = %s"

    with get_cursor(db) as cur:
        cur.execute(sql, (*updates.values(), order_id))
        if cur.rowcount == 0:
            raise HTTPException(status_code=404, detail="Order not found")

        # If status changed → append new event (append-only, never update events)
        if "status" in updates:
            cur.execute(
                """
                INSERT INTO order_events (order_id, event_type, triggered_by)
                VALUES (%s, %s, 'system')
                """,
                (order_id, updates["status"]),
            )

        cur.execute("SELECT * FROM orders WHERE order_id = %s", (order_id,))
        return cur.fetchone()


@router.delete("/{order_id}", status_code=204)
def cancel_order(order_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """
    Cancel an order — sets status to 'cancelled'.
    Appends a cancelled event to order_events.
    Only allowed if order is not already delivered.
    """
    with get_cursor(db) as cur:
        cur.execute(
            "SELECT status FROM orders WHERE order_id = %s", (order_id,)
        )
        row = cur.fetchone()
        if not row:
            raise HTTPException(status_code=404, detail="Order not found")
        if row["status"] == "delivered":
            raise HTTPException(
                status_code=400, detail="Cannot cancel a delivered order"
            )

        cur.execute(
            "UPDATE orders SET status = 'cancelled' WHERE order_id = %s", (order_id,)
        )
        cur.execute(
            """
            INSERT INTO order_events (order_id, event_type, triggered_by)
            VALUES (%s, 'cancelled', 'system')
            """,
            (order_id,),
        )


# ===========================================================================
# Order Items
# ===========================================================================

@router.get("/{order_id}/items", response_model=list[OrderItemResponse])
def get_order_items(order_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get all line items for an order."""
    with get_cursor(db) as cur:
        cur.execute(
            "SELECT * FROM order_items WHERE order_id = %s", (order_id,)
        )
        return cur.fetchall()


@router.post("/{order_id}/items", response_model=OrderItemResponse, status_code=201)
def add_order_item(
    order_id: int,
    payload: OrderItemCreate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """Add a line item to an order. Only allowed while order is in 'created' state."""
    with get_cursor(db) as cur:
        cur.execute(
            "SELECT status FROM orders WHERE order_id = %s", (order_id,)
        )
        order = cur.fetchone()
        if not order:
            raise HTTPException(status_code=404, detail="Order not found")
        if order["status"] != "created":
            raise HTTPException(
                status_code=400,
                detail="Items can only be added while order is in 'created' state"
            )

        cur.execute(
            """
            INSERT INTO order_items (order_id, item_id, quantity, unit_price)
            VALUES (%s, %s, %s, %s)
            """,
            (order_id, payload.item_id, payload.quantity, payload.unit_price),
        )
        new_id = cur.lastrowid
        cur.execute("SELECT * FROM order_items WHERE id = %s", (new_id,))
        return cur.fetchone()


# ===========================================================================
# Order Events (append-only log)
# ===========================================================================

@router.get("/{order_id}/events", response_model=list[OrderEventResponse])
def get_order_events(order_id: int, db: MySQLdb.Connection = Depends(get_db)):
    """Get the full event history for an order (ordered chronologically)."""
    with get_cursor(db) as cur:
        cur.execute(
            """
            SELECT * FROM order_events
            WHERE order_id = %s
            ORDER BY event_timestamp ASC
            """,
            (order_id,),
        )
        return cur.fetchall()


@router.post("/{order_id}/events", response_model=OrderEventResponse, status_code=201)
def append_order_event(
    order_id: int,
    payload: OrderEventCreate,
    db: MySQLdb.Connection = Depends(get_db),
):
    """
    Manually append an event to the order event log.
    Events are append-only — existing events are never updated.
    """
    with get_cursor(db) as cur:
        cur.execute(
            "SELECT order_id FROM orders WHERE order_id = %s", (order_id,)
        )
        if not cur.fetchone():
            raise HTTPException(status_code=404, detail="Order not found")

        cur.execute(
            """
            INSERT INTO order_events (order_id, event_type, triggered_by, notes)
            VALUES (%s, %s, %s, %s)
            """,
            (order_id, payload.event_type, payload.triggered_by, payload.notes),
        )
        new_id = cur.lastrowid
        cur.execute("SELECT * FROM order_events WHERE id = %s", (new_id,))
        return cur.fetchone()