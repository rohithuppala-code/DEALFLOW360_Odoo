from fastapi import APIRouter

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.permissions import is_customer
from app.services.dashboard import DashboardService
from app.utils.response import ok

router = APIRouter()
svc = DashboardService()


def _guard(user):
    if is_customer(user):
        raise AppError("FORBIDDEN", "Internal analytics are not available in the customer portal.", 403)


@router.get("/summary")
def summary(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.summary(db))


@router.get("/pipeline")
def pipeline(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.pipeline(db))


@router.get("/margins")
def margins(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.margins(db))


@router.get("/risks")
def risks(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.risks(db))


@router.get("/deal-health")
def deal_health(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.deal_health(db))


@router.get("/approvals")
def approvals(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.approvals(db))


@router.get("/warehouses")
def warehouses(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.warehouses(db))


@router.get("/subscriptions")
def subscriptions(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.subscriptions(db))


@router.get("/activity")
def activity(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.activity(db))


@router.get("/actions")
def actions(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.actions(db, user))
