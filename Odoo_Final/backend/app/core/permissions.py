from app.core.exceptions import AppError
from app.models.enums import UserRole

INTERNAL_ROLES = {
    UserRole.SALES_REP,
    UserRole.SALES_MANAGER,
    UserRole.FINANCE,
    UserRole.OPERATIONS,
    UserRole.ADMIN,
}

APPROVER_ROLES = {UserRole.SALES_MANAGER, UserRole.FINANCE, UserRole.ADMIN}
FINANCE_ROLES = {UserRole.FINANCE, UserRole.ADMIN, UserRole.SALES_MANAGER}
OPS_ROLES = {UserRole.OPERATIONS, UserRole.ADMIN, UserRole.FINANCE}
ADMIN_ROLES = {UserRole.ADMIN}
QUOTE_EDITOR_ROLES = {UserRole.SALES_REP, UserRole.SALES_MANAGER, UserRole.ADMIN}
ANALYTICS_ROLES = {UserRole.SALES_MANAGER, UserRole.FINANCE, UserRole.ADMIN, UserRole.OPERATIONS}
FULFILLMENT_ROLES = {UserRole.OPERATIONS, UserRole.FINANCE, UserRole.ADMIN, UserRole.SALES_MANAGER}
BILLING_VIEW_ROLES = {UserRole.FINANCE, UserRole.ADMIN, UserRole.SALES_MANAGER, UserRole.OPERATIONS}
BILLING_MUTATE_ROLES = {UserRole.FINANCE, UserRole.ADMIN}


def assert_role(user, allowed: set[UserRole], message: str = "You do not have permission to perform this action.") -> None:
    if user.role not in allowed and user.role != UserRole.ADMIN:
        raise AppError("FORBIDDEN", message, 403)


def can_view_costs(user) -> bool:
    return user.role in {UserRole.SALES_REP, UserRole.SALES_MANAGER, UserRole.FINANCE, UserRole.ADMIN, UserRole.OPERATIONS}


def is_customer(user) -> bool:
    return user.role == UserRole.CUSTOMER


def can_see_internal(user) -> bool:
    return user.role in INTERNAL_ROLES
