from typing import Any


def ok(data: Any = None, message: str | None = None) -> dict:
    return {"success": True, "data": data, "message": message}


def page(items: list, total: int, page_num: int, page_size: int) -> dict:
    return ok(
        {
            "items": items,
            "total": total,
            "page": page_num,
            "page_size": page_size,
            "pages": (total + page_size - 1) // page_size if page_size else 0,
        }
    )
