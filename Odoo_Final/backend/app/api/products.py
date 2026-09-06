from fastapi import APIRouter, Query
from sqlalchemy.orm import joinedload, selectinload

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.models.catalog import Product, ProductCategory
from app.models.intelligence import RecommendationRule
from app.services.serialize import product_out
from app.utils.pagination import paginate
from app.utils.response import ok, page

router = APIRouter()


@router.get("")
def list_products(
    db: DbSession,
    user: CurrentUser,
    q: str | None = None,
    category_id: int | None = None,
    product_type: str | None = None,
    page_num: int = Query(1, alias="page"),
    page_size: int = 50,
):
    query = (
        db.query(Product)
        .options(joinedload(Product.category), selectinload(Product.variants))
        .filter(Product.is_active.is_(True))
    )
    if q:
        like = f"%{q}%"
        query = query.filter(Product.name.ilike(like) | Product.sku.ilike(like))
    if category_id:
        query = query.filter(Product.category_id == category_id)
    if product_type:
        query = query.filter(Product.product_type == product_type)
    query = query.order_by(Product.name)
    items, total, p, ps = paginate(query, page_num, page_size)
    return page([product_out(x) for x in items], total, p, ps)


@router.get("/categories")
def categories(db: DbSession, user: CurrentUser):
    rows = db.query(ProductCategory).order_by(ProductCategory.name).all()
    return ok([{"id": c.id, "name": c.name, "kind": c.kind.value, "description": c.description} for c in rows])


@router.get("/{product_id}")
def get_product(product_id: int, db: DbSession, user: CurrentUser):
    p = db.get(Product, product_id)
    if not p:
        raise AppError("NOT_FOUND", "Product not found.", 404)
    return ok(product_out(p))


@router.get("/{product_id}/recommendations")
def product_recs(product_id: int, db: DbSession, user: CurrentUser):
    rules = (
        db.query(RecommendationRule)
        .filter(RecommendationRule.product_id == product_id, RecommendationRule.is_active.is_(True))
        .all()
    )
    return ok(
        [
            {
                "id": r.id,
                "type": r.recommendation_type.value,
                "product": product_out(r.recommended_product) if r.recommended_product else None,
                "reason": r.reason,
                "priority": r.priority,
            }
            for r in rules
        ]
    )
