from datetime import datetime
from io import BytesIO, StringIO
import csv

from fastapi import APIRouter, Query
from fastapi.responses import Response, StreamingResponse

from app.core.dependencies import CurrentUser, DbSession
from app.core.exceptions import AppError
from app.core.permissions import ANALYTICS_ROLES, is_customer
from app.services.reports import ReportService
from app.utils.response import ok

router = APIRouter()
svc = ReportService()


def _guard(user):
    if is_customer(user) or user.role not in ANALYTICS_ROLES:
        raise AppError("FORBIDDEN", "Not available.", 403)


def _filters(
    from_date: str | None,
    to_date: str | None,
    sales_rep_id: int | None,
    approval_status: str | None,
    status: str | None,
    product_id: int | None,
    category_id: int | None,
) -> dict:
    out: dict = {}
    if from_date:
        out["from_date"] = datetime.fromisoformat(from_date)
    if to_date:
        out["to_date"] = datetime.fromisoformat(to_date)
    if sales_rep_id:
        out["sales_rep_id"] = sales_rep_id
    if approval_status:
        out["approval_status"] = approval_status
    if status:
        out["status"] = status
    if product_id:
        out["product_id"] = product_id
    if category_id:
        out["category_id"] = category_id
    return out


@router.get("/sales")
def sales(
    db: DbSession,
    user: CurrentUser,
    from_date: str | None = None,
    to_date: str | None = None,
    sales_rep_id: int | None = None,
    approval_status: str | None = None,
    status: str | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
):
    _guard(user)
    return ok(svc.sales(db, _filters(from_date, to_date, sales_rep_id, approval_status, status, product_id, category_id)))


@router.get("/margin")
def margin(
    db: DbSession,
    user: CurrentUser,
    from_date: str | None = None,
    to_date: str | None = None,
    sales_rep_id: int | None = None,
    approval_status: str | None = None,
    status: str | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
):
    _guard(user)
    return ok(svc.margin(db, _filters(from_date, to_date, sales_rep_id, approval_status, status, product_id, category_id)))


@router.get("/discounts")
def discounts(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.discounts(db))


@router.get("/approvals")
def approvals(db: DbSession, user: CurrentUser, approval_status: str | None = None):
    _guard(user)
    return ok(svc.approvals(db, {"approval_status": approval_status} if approval_status else None))


@router.get("/fulfillment")
def fulfillment(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.fulfillment(db))


@router.get("/subscriptions")
def subscriptions(db: DbSession, user: CurrentUser):
    _guard(user)
    return ok(svc.subscriptions(db))


@router.get("/export")
def export_reports(
    db: DbSession,
    user: CurrentUser,
    format: str = Query("csv"),
    from_date: str | None = None,
    to_date: str | None = None,
    sales_rep_id: int | None = None,
    approval_status: str | None = None,
    status: str | None = None,
    product_id: int | None = None,
    category_id: int | None = None,
):
    _guard(user)
    filters = _filters(from_date, to_date, sales_rep_id, approval_status, status, product_id, category_id)
    rows = svc.table(db, filters)
    headers = ["quote_number", "customer", "sales_rep", "status", "approval_status", "total", "margin", "discount", "created_at"]
    fmt = (format or "csv").lower()
    if fmt in ("xls", "xlsx"):
        xml = _as_excel_xml(headers, rows)
        return Response(
            content=xml.encode("utf-8"),
            media_type="application/vnd.ms-excel",
            headers={"Content-Disposition": "attachment; filename=dealflow-report.xls"},
        )
    if fmt == "pdf":
        return Response(
            content=_as_pdf(rows),
            media_type="application/pdf",
            headers={"Content-Disposition": "attachment; filename=dealflow-report.pdf"},
        )
    buf = StringIO()
    writer = csv.DictWriter(buf, fieldnames=headers)
    writer.writeheader()
    for r in rows:
        writer.writerow(r)
    return Response(
        content=buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=dealflow-report.csv"},
    )


def _as_excel_xml(headers: list[str], rows: list[dict]) -> str:
    cells = "".join(f"<Cell><Data ss:Type=\"String\">{h}</Data></Cell>" for h in headers)
    body = [f"<Row>{cells}</Row>"]
    for r in rows:
        tds = "".join(f"<Cell><Data ss:Type=\"String\">{r.get(h, '')}</Data></Cell>" for h in headers)
        body.append(f"<Row>{tds}</Row>")
    return (
        '<?xml version="1.0"?>'
        '<Workbook xmlns="urn:schemas-microsoft-com:office:spreadsheet" xmlns:ss="urn:schemas-microsoft-com:office:spreadsheet">'
        "<Worksheet ss:Name=\"Report\"><Table>"
        + "".join(body)
        + "</Table></Worksheet></Workbook>"
    )


def _as_pdf(rows: list[dict]) -> bytes:
    lines = ["DealFlow360 report", ""]
    for r in rows[:80]:
        lines.append(f"{r['quote_number']}  {r['customer']}  {r['status']}  {r['total']}")
    text = "\\n".join(lines).replace("(", "\\(").replace(")", "\\)")
    stream = f"BT /F1 10 Tf 40 800 Td ({text[:1800]}) Tj ET"
    objects = [
        "1 0 obj << /Type /Catalog /Pages 2 0 R >> endobj",
        "2 0 obj << /Type /Pages /Kids [3 0 R] /Count 1 >> endobj",
        "3 0 obj << /Type /Page /Parent 2 0 R /MediaBox [0 0 612 792] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >> endobj",
        f"4 0 obj << /Length {len(stream)} >> stream\n{stream}\nendstream endobj",
        "5 0 obj << /Type /Font /Subtype /Type1 /BaseFont /Helvetica >> endobj",
    ]
    pdf = "%PDF-1.1\n"
    offsets = [0]
    for obj in objects:
        offsets.append(len(pdf))
        pdf += obj + "\n"
    xref = len(pdf)
    pdf += f"xref\n0 {len(objects)+1}\n0000000000 65535 f \n"
    for off in offsets[1:]:
        pdf += f"{off:010d} 00000 n \n"
    pdf += f"trailer << /Size {len(objects)+1} /Root 1 0 R >>\nstartxref\n{xref}\n%%EOF"
    return pdf.encode("latin-1", errors="replace")
