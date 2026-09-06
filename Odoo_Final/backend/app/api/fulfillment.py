from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.permissions import FULFILLMENT_ROLES
from app.models.enums import UserRole
from app.models.fulfillment import Inventory, Warehouse
from app.services.fulfillment import WarehouseAllocationService
from app.utils.pagination import paginate
from app.utils.response import ok, page

router = APIRouter()
fulfill_svc = WarehouseAllocationService()


def _assert_fulfillment(user):
    if user.role not in FULFILLMENT_ROLES:
        raise AppError("FORBIDDEN", "Fulfillment is limited to finance and operations.", 403)


@router.get("/warehouses")
def warehouses(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    if user.role == UserRole.CUSTOMER:
        raise AppError("FORBIDDEN", "Not available.", 403)
    query = db.query(Warehouse).order_by(Warehouse.name)
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page(
            [
                {
                    "id": w.id,
                    "name": w.name,
                    "code": w.code,
                    "city": w.city,
                    "shipping_zone": w.shipping_zone,
                }
                for w in items
            ],
            total,
            p,
            ps,
        )
    rows = query.all()
    return ok(
        [
            {
                "id": w.id,
                "name": w.name,
                "code": w.code,
                "city": w.city,
                "shipping_zone": w.shipping_zone,
            }
            for w in rows
        ]
    )


@router.get("/inventory")
def inventory(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    if user.role == UserRole.CUSTOMER:
        raise AppError("FORBIDDEN", "Not available.", 403)
    query = db.query(Inventory).order_by(Inventory.id)
    if page_num is not None or page_size is not None:
        items, total, p, ps = paginate(query, page_num or 1, page_size or 20)
        return page(
            [
                {
                    "id": r.id,
                    "warehouse_id": r.warehouse_id,
                    "warehouse": r.warehouse.name if r.warehouse else None,
                    "city": r.warehouse.city if r.warehouse else None,
                    "product_id": r.product_id,
                    "product": r.product.name if r.product else None,
                    "sku": r.product.sku if r.product else None,
                    "available_qty": r.available_qty,
                    "reserved_qty": r.reserved_qty,
                    "free": r.available_qty - r.reserved_qty,
                    "reorder_level": r.reorder_level,
                    "expected_replenishment": str(r.expected_replenishment) if r.expected_replenishment else None,
                }
                for r in items
            ],
            total,
            p,
            ps,
        )
    rows = query.all()
    return ok(
        [
            {
                "id": r.id,
                "warehouse_id": r.warehouse_id,
                "warehouse": r.warehouse.name if r.warehouse else None,
                "city": r.warehouse.city if r.warehouse else None,
                "product_id": r.product_id,
                "product": r.product.name if r.product else None,
                "sku": r.product.sku if r.product else None,
                "available_qty": r.available_qty,
                "reserved_qty": r.reserved_qty,
                "free": r.available_qty - r.reserved_qty,
                "reorder_level": r.reorder_level,
                "expected_replenishment": str(r.expected_replenishment) if r.expected_replenishment else None,
            }
            for r in rows
        ]
    )


@router.get("/fulfillment/queue")
def fulfillment_queue(
    db: DbSession,
    user: CurrentUser,
    page_num: int | None = Query(None, alias="page"),
    page_size: int | None = Query(None, alias="page_size"),
):
    _assert_fulfillment(user)
    items = fulfill_svc.queue(db)
    if page_num is not None or page_size is not None:
        p = page_num or 1
        ps = page_size or 20
        total = len(items)
        start = (p - 1) * ps
        paged = items[start : start + ps]
        return page(paged, total, p, ps)
    return ok(items)
