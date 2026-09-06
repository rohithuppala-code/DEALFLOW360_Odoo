from fastapi import APIRouter, Query

from app.core.dependencies import CurrentUser, DbSession
from app.core.permissions import is_customer
from app.models.billing import Invoice
from app.models.customer import Customer
from app.models.catalog import Product
from app.models.ops import Order
from app.models.quote import Quote
from app.services.access import customer_scope_filter
from app.utils.response import ok

router = APIRouter()


@router.get("")
def search(q: str, db: DbSession, user: CurrentUser, limit: int = Query(8, le=20)):
    if not q or len(q.strip()) < 2:
        return ok({"customers": [], "quotes": [], "products": [], "orders": [], "invoices": []})
    like = f"%{q.strip()}%"
    cq = db.query(Customer).filter(Customer.name.ilike(like) | Customer.code.ilike(like))
    qq = db.query(Quote).filter(Quote.quote_number.ilike(like) | Quote.title.ilike(like))
    pq = db.query(Product).filter(Product.name.ilike(like) | Product.sku.ilike(like), Product.is_active.is_(True))
    oq = db.query(Order).filter(Order.order_number.ilike(like))
    iq = db.query(Invoice).filter(Invoice.invoice_number.ilike(like))
    if is_customer(user):
        cq = cq.filter(customer_scope_filter(Customer.id, db, user))
        qq = qq.filter(customer_scope_filter(Quote.customer_id, db, user), Quote.sent_to_customer_at.isnot(None))
        oq = oq.filter(customer_scope_filter(Order.customer_id, db, user))
        iq = iq.filter(customer_scope_filter(Invoice.customer_id, db, user))
    return ok(
        {
            "customers": [{"id": c.id, "name": c.name, "code": c.code} for c in cq.limit(limit)],
            "quotes": [{"id": x.id, "quote_number": x.quote_number, "title": x.title, "total": float(x.total)} for x in qq.limit(limit)],
            "products": [{"id": p.id, "sku": p.sku, "name": p.name, "price": float(p.base_price)} for p in pq.limit(limit)],
            "orders": [{"id": o.id, "order_number": o.order_number, "total": float(o.total)} for o in oq.limit(limit)],
            "invoices": [{"id": i.id, "invoice_number": i.invoice_number, "total": float(i.total)} for i in iq.limit(limit)],
        }
    )
