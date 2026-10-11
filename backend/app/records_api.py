"""GET /companies, GET /metrics, GET /compare: clean financial records built from stored metrics."""
import logging
from typing import Literal, Optional

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.api_contract import ApiError, ErrorResponse
from app.database import get_db
from app.models import Company, Document, Metric
from app.records_logic import (
    basis_compatible, build_records, choose, normalize_period,
    parse_metric_name, period_sort_key,
)

logger = logging.getLogger(__name__)
router = APIRouter()

METRIC_ORDER = ["revenue", "gross_margin", "operating_income", "operating_margin",
                "net_income", "eps", "free_cash_flow"]


def _metric_key(metric: str) -> tuple[int, str]:
    return (METRIC_ORDER.index(metric) if metric in METRIC_ORDER else len(METRIC_ORDER), metric)


# ---------- Response models ----------

class Alternative(BaseModel):
    value: float
    unit: Optional[str] = None
    basis: Optional[str] = None
    source_type: Optional[str] = Field(None, examples=["transcript"])
    source_filename: Optional[str] = None


class MetricRecord(BaseModel):
    company: str = Field(..., examples=["NVIDIA"])
    ticker: Optional[str] = Field(None, examples=["NVDA"])
    metric: str = Field(..., examples=["revenue"])
    basis: Optional[str] = Field(None, description="GAAP, non-GAAP, or null if the source did not say.")
    period: str = Field(..., examples=["Q2 FY27"])
    value: float
    unit: Optional[str] = Field(None, examples=["USD_million"])
    source_document_id: int
    source_filename: Optional[str] = None
    source_type: Optional[str] = Field(None, examples=["commentary"])
    conflict: bool = Field(False, description="True if another source disagrees by more than 2%.")
    alternatives: list[Alternative] = Field([], description="The disagreeing values, when conflict is true.")


class MetricList(BaseModel):
    items: list[MetricRecord]
    total: int


class CompanyInfo(BaseModel):
    company_id: int
    name: str
    ticker: Optional[str] = None
    periods: list[str] = Field(..., examples=[["Q4 FY26", "Q1 FY27", "Q2 FY27"]])
    metrics: list[str]


class CompanyList(BaseModel):
    items: list[CompanyInfo]


class CompareRow(BaseModel):
    metric: str
    unit: Optional[str] = None
    basis_a: Optional[str] = None
    basis_b: Optional[str] = None
    value_a: Optional[float] = None
    value_b: Optional[float] = None
    change: Optional[float] = Field(None, description="value_b minus value_a.")
    change_unit: Optional[Literal["absolute", "percentage_points"]] = None
    change_pct: Optional[float] = Field(None, description="Percent change; null for margins (use change in percentage points).")
    conflict_a: bool = False
    conflict_b: bool = False
    source_a: Optional[str] = None
    source_b: Optional[str] = None
    note: Optional[str] = None


class CompareResponse(BaseModel):
    company: str
    ticker: Optional[str] = None
    period_a: str
    period_b: str
    rows: list[CompareRow]
    notes: list[str] = []


# ---------- Helpers ----------

def _find_company(db: Session, text: str) -> Company:
    t = text.strip().lower()
    company = db.scalar(select(Company).where(func.lower(Company.ticker) == t))
    if company is None:
        company = db.scalar(select(Company).where(func.lower(Company.name) == t))
    if company is None:
        raise ApiError(404, "company_not_found", f"No company matches '{text}'.")
    return company


def _load(db: Session, company_id: Optional[int] = None) -> list[dict]:
    query = select(Metric, Document).join(Document, Metric.source_document_id == Document.id)
    if company_id is not None:
        query = query.where(Metric.company_id == company_id)
    rows = [
        dict(id=m.id, name=m.name, value=m.value, unit=m.unit, period=m.period,
             document_id=d.id, doc_type=d.document_type, filename=d.filename,
             company_id=m.company_id)
        for m, d in db.execute(query).all()
    ]
    owner = {r["document_id"]: r["company_id"] for r in rows}
    records = build_records(rows)
    for rec in records:
        rec["company_id"] = owner[rec["document_id"]]
    return records


def _parse_metric_param(metric: Optional[str], basis: Optional[str]):
    if not metric:
        return None, basis
    cleaned = metric.strip().lower().replace("-", "_").replace(" ", "_")
    base, suffix_basis = parse_metric_name(cleaned)
    return base, basis or suffix_basis


def _alt(r: dict) -> Alternative:
    return Alternative(value=r["value"], unit=r["unit"], basis=r["basis"],
                       source_type=r["doc_type"], source_filename=r["filename"])


# ---------- Endpoints ----------

@router.get("/companies", response_model=CompanyList, tags=["records"],
            summary="Companies with the periods and metrics available for each")
def list_companies(db: Session = Depends(get_db)):
    records = _load(db)
    out = []
    for c in db.scalars(select(Company).order_by(Company.id)).all():
        mine = [r for r in records if r["company_id"] == c.id]
        out.append(CompanyInfo(
            company_id=c.id, name=c.name, ticker=c.ticker,
            periods=sorted({r["period"] for r in mine}, key=period_sort_key),
            metrics=sorted({r["metric"] for r in mine}, key=_metric_key),
        ))
    return CompanyList(items=out)


@router.get(
    "/metrics", response_model=MetricList, tags=["records"],
    summary="Clean financial records: query by company, metric, period and basis",
    description="One best value per company, metric and period. Periods are normalised "
    "(Q2 fiscal 2027 and Q2FY27 both mean Q2 FY27) and money totals are in millions of USD. "
    "When sources disagree by more than 2%, conflict is true and the other values are listed "
    "under alternatives. Source priority: GAAP, then unlabeled, then non-GAAP; filings over "
    "CFO commentary over call transcripts.",
    responses={404: {"model": ErrorResponse, "description": "company_not_found"},
               422: {"model": ErrorResponse, "description": "invalid_period"}},
)
def list_metrics(
    company: Optional[str] = None,
    metric: Optional[str] = None,
    period: Optional[str] = None,
    basis: Optional[Literal["GAAP", "non-GAAP"]] = None,
    db: Session = Depends(get_db),
):
    comp = _find_company(db, company) if company else None
    period_norm = None
    if period:
        period_norm = normalize_period(period)
        if period_norm is None:
            raise ApiError(422, "invalid_period",
                           f"Could not read period '{period}'. Use a format like 'Q2 FY27'.")
    metric_base, basis = _parse_metric_param(metric, basis)

    records = _load(db, comp.id if comp else None)
    companies = {c.id: c for c in db.scalars(select(Company)).all()}
    groups: dict = {}
    for r in records:
        groups.setdefault((r["company_id"], r["metric"], r["period"]), []).append(r)

    picked = []
    for (cid, m, p), group in groups.items():
        if metric_base and m != metric_base:
            continue
        if period_norm and p != period_norm:
            continue
        best, conflicts = choose(group, basis)
        if best is not None:
            picked.append((cid, m, p, best, conflicts))
    picked.sort(key=lambda x: (companies[x[0]].name, _metric_key(x[1]), period_sort_key(x[2])))

    items = [
        MetricRecord(
            company=companies[cid].name, ticker=companies[cid].ticker, metric=m,
            basis=best["basis"], period=p, value=best["value"], unit=best["unit"],
            source_document_id=best["document_id"], source_filename=best["filename"],
            source_type=best["doc_type"], conflict=bool(conflicts),
            alternatives=[_alt(c) for c in conflicts],
        )
        for cid, m, p, best, conflicts in picked
    ]
    return MetricList(items=items, total=len(items))


@router.get(
    "/compare", response_model=CompareResponse, tags=["records"],
    summary="Compare two periods for a company",
    description="Returns one row per metric with both values and the change from period_a to "
    "period_b. Margins show the change in percentage points. Metrics found in only one period "
    "still appear, with a note. Period spellings are normalised. company is optional while only "
    "one company exists.",
    responses={404: {"model": ErrorResponse, "description": "company_not_found / no_data_for_periods"},
               422: {"model": ErrorResponse, "description": "invalid_period / same_period / company_required"}},
)
def compare(
    period_a: str,
    period_b: str,
    company: Optional[str] = None,
    metric: Optional[str] = None,
    basis: Optional[Literal["GAAP", "non-GAAP"]] = None,
    db: Session = Depends(get_db),
):
    pa, pb = normalize_period(period_a), normalize_period(period_b)
    for raw, norm in ((period_a, pa), (period_b, pb)):
        if norm is None:
            raise ApiError(422, "invalid_period",
                           f"Could not read period '{raw}'. Use a format like 'Q2 FY27'.")
    if pa == pb:
        raise ApiError(422, "same_period", "Choose two different periods to compare.")

    if company:
        comp = _find_company(db, company)
    else:
        companies = db.scalars(select(Company)).all()
        if not companies:
            raise ApiError(404, "company_not_found", "No companies exist yet.")
        if len(companies) > 1:
            raise ApiError(422, "company_required", "Several companies exist; pass ?company=TICKER.")
        comp = companies[0]

    metric_base, basis = _parse_metric_param(metric, basis)
    records = _load(db, comp.id)
    by: dict = {}
    for r in records:
        by.setdefault((r["metric"], r["period"]), []).append(r)

    metrics = sorted({k[0] for k in by if k[1] in (pa, pb)}, key=_metric_key)
    if metric_base:
        metrics = [m for m in metrics if m == metric_base]
    if not metrics:
        raise ApiError(404, "no_data_for_periods", f"No stored metrics for {pa} or {pb}.")

    rows, rounded = [], False
    for m in metrics:
        a, ca = choose(by.get((m, pa), []), basis)
        b, cb = choose(by.get((m, pb), []), basis)
        notes_row, change, change_pct, change_unit = [], None, None, None
        if a and b:
            if not basis_compatible(a["basis"], b["basis"]):
                notes_row.append(f"Different basis ({a['basis']} vs {b['basis']}); change not computed.")
            elif a["unit"] != b["unit"]:
                notes_row.append(f"Different units ({a['unit']} vs {b['unit']}); change not computed.")
            else:
                change = round(b["value"] - a["value"], 4)
                if a["unit"] == "percent":
                    change_unit = "percentage_points"
                else:
                    change_unit = "absolute"
                    if a["value"]:
                        change_pct = round(change / abs(a["value"]) * 100, 2)
        elif a:
            notes_row.append(f"Only available in {pa}.")
        elif b:
            notes_row.append(f"Only available in {pb}.")
        if ca or cb:
            notes_row.append("Sources disagree; see /metrics for the alternatives.")
        for r in (a, b):
            if r and r["doc_type"] == "transcript" and r["original_unit"] == "USD_billion":
                rounded = True
        rows.append(CompareRow(
            metric=m, unit=(a or b)["unit"],
            basis_a=a["basis"] if a else None, basis_b=b["basis"] if b else None,
            value_a=a["value"] if a else None, value_b=b["value"] if b else None,
            change=change, change_unit=change_unit, change_pct=change_pct,
            conflict_a=bool(ca), conflict_b=bool(cb),
            source_a=a["filename"] if a else None, source_b=b["filename"] if b else None,
            note=" ".join(notes_row) or None,
        ))

    notes = [f"No stored metrics for {p}." for p in (pa, pb) if not any(k[1] == p for k in by)]
    if rounded:
        notes.append("Some values come from call transcripts and are rounded (e.g. '$68 billion').")
    return CompareResponse(company=comp.name, ticker=comp.ticker, period_a=pa, period_b=pb,
                           rows=rows, notes=notes)
