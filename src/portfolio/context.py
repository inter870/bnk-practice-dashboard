from __future__ import annotations

import csv
from dataclasses import asdict, dataclass, field, replace
from datetime import date, datetime
import io
import math
import re
from typing import Any, Iterable, Literal, Mapping, Sequence

from src.institutional.models import DataSourceMeta, ProviderResult

from .models import ASSET_CLASSES, Holding


DEFAULT_HISTORY_MIN_DAYS = 60
DEFAULT_HISTORY_MIN_COVERAGE = 0.80


def _get(item: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        if isinstance(item, Mapping) and name in item:
            return item.get(name)
        if hasattr(item, name):
            return getattr(item, name)
    return default


def _finite(value: Any) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError):
        return None
    return number if math.isfinite(number) else None


def _unique(values: Iterable[str]) -> tuple[str, ...]:
    return tuple(dict.fromkeys(str(value) for value in values if str(value)))


def _default_meta(
    currency: str,
    source: str = "legacy_portfolio_csv",
    as_of_date: str | None = None,
) -> DataSourceMeta:
    available_at = str(as_of_date).strip() if as_of_date else None
    return DataSourceMeta(
        source=source,
        provider="manual",
        source_url=None,
        as_of_date=available_at[:10] if available_at else None,
        available_at=available_at,
        fetched_at=None,
        frequency="snapshot",
        unit=currency,
        quality_score=0,
        is_fallback=False,
        stale_data_flag=available_at is None,
        source_table_or_endpoint="sidebar:portfolio_holdings_text",
        currency=currency,
        data_mode="manual",
        quality_flags=("manual_input",) if available_at else ("manual_input", "timestamp_missing"),
        missing_data_flag=available_at is None,
    )


def _meta_with_as_of(meta: DataSourceMeta, as_of_date: str | None) -> DataSourceMeta:
    if not as_of_date:
        return meta
    available_at = str(as_of_date).strip()
    flags = tuple(flag for flag in meta.quality_flags if flag != "timestamp_missing")
    return replace(
        meta,
        as_of_date=available_at[:10],
        available_at=available_at,
        stale_data_flag=False,
        missing_data_flag=False,
        quality_flags=flags,
    )


def _meta_with_diagnostics(
    meta: DataSourceMeta,
    *,
    warnings: Iterable[str] = (),
    quality_flags: Iterable[str] = (),
    error_code: str | None = None,
) -> DataSourceMeta:
    return replace(
        meta,
        warnings=_unique((*meta.warnings, *warnings)),
        quality_flags=_unique((*meta.quality_flags, *quality_flags)),
        error_code=error_code,
    )


@dataclass(frozen=True)
class PortfolioValidationIssue:
    code: str
    message: str
    field: str | None = None
    row_number: int | None = None
    severity: Literal["error", "warning"] = "error"

    def __str__(self) -> str:
        location = f"row[{self.row_number}]." if self.row_number is not None else ""
        field = f"{self.field}:" if self.field else ""
        return f"{location}{field}{self.code}: {self.message}"

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class PortfolioContextValidationError(ValueError):
    def __init__(self, issues: Sequence[PortfolioValidationIssue]):
        self.issues = tuple(issues)
        super().__init__("; ".join(str(issue) for issue in self.issues))


def _holding_market_value(holding: Any) -> float:
    quantity = _finite(_get(holding, "quantity", "qty")) or 0.0
    current_price = _finite(_get(holding, "current_price", "currentPrice", "latest", "price")) or 0.0
    return quantity * current_price


def _portfolio_validation_issues(
    holdings: Sequence[Any],
    cash: Any,
    declared_total: Any,
    currency: Any,
) -> tuple[PortfolioValidationIssue, ...]:
    issues: list[PortfolioValidationIssue] = []
    cash_value = _finite(cash)
    declared_value = _finite(declared_total) if declared_total is not None else None
    if cash_value is None:
        issues.append(PortfolioValidationIssue("cash_not_finite", "cash must be a finite number", "cash"))
    elif cash_value < 0:
        issues.append(PortfolioValidationIssue("negative_cash", "cash must be non-negative", "cash"))

    if declared_total is not None:
        if declared_value is None:
            issues.append(
                PortfolioValidationIssue(
                    "declared_total_not_finite",
                    "declared_total must be a finite number",
                    "declared_total",
                )
            )
        elif declared_value < 0:
            issues.append(
                PortfolioValidationIssue(
                    "negative_declared_total",
                    "declared_total must be non-negative",
                    "declared_total",
                )
            )
    if (
        cash_value is not None
        and cash_value >= 0
        and declared_value is not None
        and declared_value >= 0
        and cash_value > declared_value
    ):
        issues.append(
            PortfolioValidationIssue(
                "cash_exceeds_declared_total",
                "cash must not exceed declared_total",
                "cash",
            )
        )

    if not str(currency or "").strip():
        issues.append(PortfolioValidationIssue("missing_currency", "currency is required", "currency"))
    portfolio_currency = str(currency or "").strip().upper()

    cash_holding_value = 0.0
    for index, holding in enumerate(holdings, start=1):
        symbol = str(_get(holding, "symbol", "code", default="") or "").strip()
        if not symbol:
            issues.append(
                PortfolioValidationIssue("missing_symbol", "holding symbol is required", "symbol", index)
            )

        quantity = _finite(_get(holding, "quantity", "qty"))
        if quantity is None:
            issues.append(
                PortfolioValidationIssue(
                    "quantity_not_finite",
                    "quantity must be a finite number",
                    "quantity",
                    index,
                )
            )
        elif quantity < 0:
            issues.append(
                PortfolioValidationIssue(
                    "negative_quantity",
                    "quantity must be non-negative",
                    "quantity",
                    index,
                )
            )

        current_price = _finite(_get(holding, "current_price", "currentPrice", "latest", "price"))
        if current_price is None:
            issues.append(
                PortfolioValidationIssue(
                    "current_price_not_finite",
                    "current_price must be a finite number",
                    "current_price",
                    index,
                )
            )
        elif current_price < 0:
            issues.append(
                PortfolioValidationIssue(
                    "negative_current_price",
                    "current_price must be non-negative",
                    "current_price",
                    index,
                )
            )

        average_cost = _finite(_get(holding, "average_cost", "averageCost", "avg_price", "avgPrice"))
        if average_cost is None:
            issues.append(
                PortfolioValidationIssue(
                    "average_cost_not_finite",
                    "average_cost must be a finite number",
                    "average_cost",
                    index,
                )
            )
        elif average_cost < 0:
            issues.append(
                PortfolioValidationIssue(
                    "negative_average_cost",
                    "average_cost must be non-negative",
                    "average_cost",
                    index,
                )
            )

        holding_currency = str(_get(holding, "currency", default=portfolio_currency) or portfolio_currency).strip().upper()
        if portfolio_currency and holding_currency != portfolio_currency:
            issues.append(
                PortfolioValidationIssue(
                    "mixed_currency_requires_fx",
                    f"{holding_currency} holding requires timestamped FX conversion into {portfolio_currency}",
                    "currency",
                    index,
                )
            )
        if str(_get(holding, "asset_class", "assetClass", default="")) == "cash":
            cash_holding_value += _holding_market_value(holding)

    if cash_value is not None and cash_value > 0 and cash_holding_value > 0:
        issues.append(
            PortfolioValidationIssue(
                "duplicate_cash_representation",
                "represent cash either as PortfolioContext.cash or as a cash holding, not both",
                "cash",
            )
        )
    return tuple(issues)


@dataclass(frozen=True)
class PortfolioContext:
    holdings: tuple[Holding, ...]
    cash: float = 0.0
    declared_total: float | None = None
    currency: str = "KRW"
    meta: DataSourceMeta | None = None
    as_of_date: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        holdings = tuple(self.holdings or ())
        currency = str(self.currency or "").strip().upper()
        issues = _portfolio_validation_issues(holdings, self.cash, self.declared_total, currency)
        if issues:
            raise PortfolioContextValidationError(issues)
        object.__setattr__(self, "holdings", holdings)
        object.__setattr__(self, "cash", float(self.cash))
        object.__setattr__(
            self,
            "declared_total",
            None if self.declared_total is None else float(self.declared_total),
        )
        object.__setattr__(self, "currency", currency)
        object.__setattr__(self, "warnings", _unique(self.warnings))

    @property
    def holdings_market_value(self) -> float:
        return sum(_holding_market_value(holding) for holding in self.holdings)

    @property
    def holdings_value(self) -> float:
        return self.holdings_market_value

    @property
    def computed_total(self) -> float:
        return self.holdings_market_value + self.cash

    @property
    def total_value(self) -> float:
        """The computed total is authoritative; declared_total is diagnostic only."""
        return self.computed_total

    @property
    def declared_total_discrepancy(self) -> float | None:
        if self.declared_total is None:
            return None
        return self.declared_total - self.computed_total

    @property
    def total_discrepancy(self) -> float | None:
        return self.declared_total_discrepancy

    @property
    def absolute_declared_total_discrepancy(self) -> float | None:
        discrepancy = self.declared_total_discrepancy
        return None if discrepancy is None else abs(discrepancy)

    @property
    def declared_total_discrepancy_ratio(self) -> float | None:
        discrepancy = self.declared_total_discrepancy
        if discrepancy is None or self.computed_total <= 0:
            return None
        return discrepancy / self.computed_total

    @property
    def source_meta(self) -> DataSourceMeta | None:
        return self.meta

    def to_dict(self) -> dict[str, Any]:
        return {
            "holdings": [asdict(holding) if hasattr(holding, "__dataclass_fields__") else dict(holding) for holding in self.holdings],
            "cash": self.cash,
            "declared_total": self.declared_total,
            "currency": self.currency,
            "as_of_date": self.as_of_date,
            "warnings": list(self.warnings),
            "holdings_market_value": self.holdings_market_value,
            "computed_total": self.computed_total,
            "declared_total_discrepancy": self.declared_total_discrepancy,
            "declared_total_discrepancy_ratio": self.declared_total_discrepancy_ratio,
            "meta": self.meta.to_dict() if self.meta else None,
        }


def validate_portfolio_context(
    context_or_holdings: PortfolioContext | Sequence[Any],
    *,
    cash: Any = None,
    declared_total: Any = None,
    currency: str = "KRW",
) -> tuple[PortfolioValidationIssue, ...]:
    if isinstance(context_or_holdings, PortfolioContext):
        return _portfolio_validation_issues(
            context_or_holdings.holdings,
            context_or_holdings.cash,
            context_or_holdings.declared_total,
            context_or_holdings.currency,
        )
    return _portfolio_validation_issues(
        tuple(context_or_holdings or ()),
        0.0 if cash is None else cash,
        declared_total,
        currency,
    )


def _issue_texts(issues: Iterable[PortfolioValidationIssue]) -> tuple[str, ...]:
    return tuple(str(issue) for issue in issues if issue.severity == "error")


def build_portfolio_context(
    holdings: Sequence[Holding],
    *,
    cash: Any = 0.0,
    declared_total: Any = None,
    currency: str = "KRW",
    meta: DataSourceMeta | None = None,
    as_of_date: str | None = None,
    warnings: Iterable[str] = (),
) -> ProviderResult[PortfolioContext]:
    source_meta = _meta_with_as_of(
        meta or _default_meta(currency, source="portfolio_context", as_of_date=as_of_date),
        as_of_date,
    )
    issues = _portfolio_validation_issues(tuple(holdings or ()), cash, declared_total, currency)
    if issues:
        errors = _issue_texts(issues)
        return ProviderResult(
            data=None,
            meta=_meta_with_diagnostics(
                source_meta,
                quality_flags=("validation_failed",),
                error_code="portfolio_validation_failed",
            ),
            status="error",
            errors=errors,
        )

    context = PortfolioContext(
        holdings=tuple(holdings or ()),
        cash=float(cash),
        declared_total=None if declared_total is None else float(declared_total),
        currency=currency,
        meta=source_meta,
        as_of_date=source_meta.as_of_date,
        warnings=_unique(warnings),
    )
    context_warnings = list(context.warnings)
    discrepancy = context.declared_total_discrepancy
    if discrepancy is not None and not math.isclose(discrepancy, 0.0, abs_tol=1e-9):
        context_warnings.append(f"declared_total_discrepancy:{discrepancy:.10g}")
    result_meta = _meta_with_diagnostics(source_meta, warnings=context_warnings)
    if result_meta is not source_meta or context.meta != result_meta:
        context = replace(context, meta=result_meta, warnings=_unique(context_warnings))
    return ProviderResult(data=context, meta=result_meta, warnings=_unique(context_warnings))


def _normalize_symbol(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, float) and math.isfinite(value) and value.is_integer():
        value = int(value)
    text = str(value).strip()
    if text.lower() in {"", "nan", "none", "null"}:
        return ""
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".", 1)[0]
    if text.isdigit():
        return text.zfill(6) if len(text) <= 6 else ""
    match = re.fullmatch(r"(\d{6})(?:\.(?:KS|KQ))?", text, flags=re.IGNORECASE)
    if match:
        return match.group(1)
    return text.upper()


def _resolve_current_price(
    row: Mapping[str, Any],
    symbol: str,
    current_prices: Mapping[str, Any] | None,
) -> float | None:
    row_price = _finite(_get(row, "current_price", "currentPrice", "latest", "price", "close"))
    if row_price is not None:
        return row_price
    if not current_prices:
        return None
    raw = current_prices.get(symbol)
    if raw is None:
        raw = next(
            (value for key, value in current_prices.items() if _normalize_symbol(key) == symbol),
            None,
        )
    direct = _finite(raw)
    if direct is not None:
        return direct
    return _finite(_get(raw, "last_close", "current_price", "currentPrice", "latest", "price", "close"))


def _adapt_legacy_row(
    row: Mapping[str, Any],
    *,
    row_number: int,
    current_prices: Mapping[str, Any] | None,
    code_to_name: Mapping[str, str] | None,
    default_currency: str,
) -> tuple[Holding | None, tuple[PortfolioValidationIssue, ...], tuple[str, ...]]:
    issues: list[PortfolioValidationIssue] = []
    warnings: list[str] = []
    symbol = _normalize_symbol(_get(row, "code", "symbol", "ticker"))
    if not symbol:
        issues.append(PortfolioValidationIssue("invalid_symbol", "code/symbol is required", "code", row_number))

    quantity = _finite(_get(row, "qty", "quantity"))
    if quantity is None:
        issues.append(
            PortfolioValidationIssue("quantity_not_finite", "qty must be a finite number", "qty", row_number)
        )
    elif quantity < 0:
        issues.append(
            PortfolioValidationIssue("negative_quantity", "qty must be non-negative", "qty", row_number)
        )

    average_cost = _finite(_get(row, "avg_price", "average_cost", "averageCost", "avgPrice"))
    if average_cost is None:
        issues.append(
            PortfolioValidationIssue(
                "average_cost_not_finite",
                "avg_price must be a finite number",
                "avg_price",
                row_number,
            )
        )
    elif average_cost < 0:
        issues.append(
            PortfolioValidationIssue(
                "negative_average_cost",
                "avg_price must be non-negative",
                "avg_price",
                row_number,
            )
        )

    current_price = _resolve_current_price(row, symbol, current_prices)
    if current_price is None:
        issues.append(
            PortfolioValidationIssue(
                "current_price_missing",
                "current price is required; average cost is not a market-price substitute",
                "current_price",
                row_number,
            )
        )
    elif current_price <= 0:
        issues.append(
            PortfolioValidationIssue(
                "current_price_not_positive",
                "current price must be positive",
                "current_price",
                row_number,
            )
        )

    raw_asset_class = str(_get(row, "asset_class", "assetClass", default="stocks") or "stocks")
    asset_class = raw_asset_class if raw_asset_class in ASSET_CLASSES else ""
    if not asset_class:
        issues.append(
            PortfolioValidationIssue(
                "invalid_asset_class",
                f"asset_class must be one of {', '.join(ASSET_CLASSES)}",
                "asset_class",
                row_number,
            )
        )

    if issues:
        return None, tuple(issues), tuple(warnings)

    names = code_to_name or {}
    name = str(_get(row, "name", default=names.get(symbol, symbol)) or names.get(symbol, symbol))
    sector_raw = _get(row, "sector")
    country_raw = _get(row, "country", default="KR" if symbol.isdigit() and len(symbol) == 6 else None)
    benchmark_raw = _get(row, "benchmark_symbol", "benchmarkSymbol", default="KS11" if country_raw == "KR" else None)
    holding = Holding(
        id=str(_get(row, "id", default=f"legacy-{symbol}") or f"legacy-{symbol}"),
        symbol=symbol,
        name=name,
        asset_class=asset_class,  # type: ignore[arg-type]
        quantity=float(quantity),
        average_cost=float(average_cost),
        current_price=float(current_price),
        currency=str(_get(row, "currency", default=default_currency) or default_currency).upper(),
        sector=None if sector_raw is None else str(sector_raw),
        country=None if country_raw is None else str(country_raw),
        benchmark_symbol=None if benchmark_raw is None else str(benchmark_raw),
    )
    return holding, (), tuple(warnings)


def adapt_legacy_csv_rows(
    rows: Iterable[Mapping[str, Any]] | Mapping[str, Any] | None,
    *,
    cash: Any = 0.0,
    declared_total: Any = None,
    current_prices: Mapping[str, Any] | None = None,
    code_to_name: Mapping[str, str] | None = None,
    currency: str = "KRW",
    meta: DataSourceMeta | None = None,
    as_of_date: str | None = None,
) -> ProviderResult[PortfolioContext]:
    source_meta = _meta_with_as_of(meta or _default_meta(currency, as_of_date=as_of_date), as_of_date)
    row_values = [rows] if isinstance(rows, Mapping) else list(rows or ())
    holdings: list[Holding] = []
    issues: list[PortfolioValidationIssue] = []
    warnings: list[str] = []
    for row_number, row in enumerate(row_values, start=1):
        if not isinstance(row, Mapping):
            issues.append(
                PortfolioValidationIssue("invalid_row", "CSV row must be a mapping", row_number=row_number)
            )
            continue
        holding, row_issues, row_warnings = _adapt_legacy_row(
            row,
            row_number=row_number,
            current_prices=current_prices,
            code_to_name=code_to_name,
            default_currency=currency,
        )
        issues.extend(row_issues)
        warnings.extend(row_warnings)
        if holding is not None:
            holdings.append(holding)

    issues.extend(_portfolio_validation_issues(tuple(holdings), cash, declared_total, currency))
    if issues:
        error_texts = _issue_texts(issues)
        error_meta = _meta_with_diagnostics(
            source_meta,
            warnings=warnings,
            quality_flags=("validation_failed",),
            error_code="legacy_csv_validation_failed",
        )
        return ProviderResult(
            data=None,
            meta=error_meta,
            status="error",
            warnings=_unique(warnings),
            errors=error_texts,
        )

    context_result = build_portfolio_context(
        holdings,
        cash=cash,
        declared_total=declared_total,
        currency=currency,
        meta=_meta_with_diagnostics(
            source_meta,
            warnings=warnings,
            quality_flags=(),
        ),
        as_of_date=as_of_date,
        warnings=warnings,
    )
    return context_result


def parse_legacy_portfolio_csv(
    text: str,
    **kwargs: Any,
) -> ProviderResult[PortfolioContext]:
    currency = str(kwargs.get("currency", "KRW"))
    source_meta = kwargs.get("meta") or _default_meta(currency)
    if not str(text or "").strip():
        return adapt_legacy_csv_rows([], **kwargs)
    try:
        reader = csv.DictReader(io.StringIO(str(text).lstrip("\ufeff").strip()))
        fieldnames = {str(name or "").strip() for name in (reader.fieldnames or ())}
        missing = {"code", "qty", "avg_price"} - fieldnames
        if missing:
            error = f"missing_required_columns:{','.join(sorted(missing))}"
            return ProviderResult(
                data=None,
                meta=_meta_with_diagnostics(
                    source_meta,
                    quality_flags=("validation_failed",),
                    error_code="legacy_csv_missing_columns",
                ),
                status="error",
                errors=(error,),
            )
        rows = list(reader)
    except (csv.Error, TypeError, ValueError) as exc:
        return ProviderResult(
            data=None,
            meta=_meta_with_diagnostics(
                source_meta,
                quality_flags=("parse_failed",),
                error_code="legacy_csv_parse_failed",
            ),
            status="error",
            errors=(f"legacy_csv_parse_failed:{exc}",),
        )
    return adapt_legacy_csv_rows(rows, **kwargs)


portfolio_context_from_legacy_rows = adapt_legacy_csv_rows
legacy_csv_rows_to_context = adapt_legacy_csv_rows


def _normalize_date(value: Any) -> str | None:
    if isinstance(value, datetime):
        return value.date().isoformat()
    if isinstance(value, date):
        return value.isoformat()
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).date().isoformat()
    except ValueError:
        try:
            return date.fromisoformat(text[:10]).isoformat()
        except ValueError:
            return None


def _series_rows(raw_series: Any) -> Iterable[tuple[Any, Any]]:
    if isinstance(raw_series, Mapping):
        if any(key in raw_series for key in ("date", "as_of_date", "timestamp")):
            yield (
                _get(raw_series, "date", "as_of_date", "timestamp"),
                _get(raw_series, "value", "price", "close", "current_price", "return", "ret"),
            )
        else:
            yield from raw_series.items()
        return
    for item in raw_series or ():
        if isinstance(item, Mapping) or hasattr(item, "date"):
            yield (
                _get(item, "date", "as_of_date", "timestamp"),
                _get(item, "value", "price", "close", "current_price", "return", "ret"),
            )
        elif isinstance(item, Sequence) and not isinstance(item, (str, bytes)) and len(item) >= 2:
            yield item[0], item[1]


def _normalize_dated_history(
    history: Mapping[str, Any] | Iterable[Any],
    symbols: Sequence[str],
) -> tuple[dict[str, dict[str, float]], tuple[str, ...]]:
    normalized_symbols = {_normalize_symbol(symbol): symbol for symbol in symbols}
    result: dict[str, dict[str, float]] = {symbol: {} for symbol in symbols}
    warnings: list[str] = []

    if isinstance(history, Mapping):
        for raw_symbol, raw_series in history.items():
            symbol = normalized_symbols.get(_normalize_symbol(raw_symbol))
            if symbol is None:
                continue
            for raw_date, raw_value in _series_rows(raw_series):
                date_key = _normalize_date(raw_date)
                value = _finite(raw_value)
                if date_key is None or value is None or value <= 0:
                    warnings.append(f"invalid_history_point:{symbol}")
                    continue
                result[symbol][date_key] = value
        return result, _unique(warnings)

    for row in history or ():
        symbol = normalized_symbols.get(_normalize_symbol(_get(row, "symbol", "code", "ticker")))
        if symbol is None:
            continue
        date_key = _normalize_date(_get(row, "date", "as_of_date", "timestamp"))
        value = _finite(_get(row, "value", "price", "close", "current_price"))
        if date_key is None or value is None or value <= 0:
            warnings.append(f"invalid_history_point:{symbol}")
            continue
        result[symbol][date_key] = value
    return result, _unique(warnings)


@dataclass(frozen=True)
class HistoryCoverage:
    expected_days: int
    aligned_days: int
    coverage_ratio: float
    symbol_coverage: dict[str, float]
    minimum_days: int = DEFAULT_HISTORY_MIN_DAYS
    minimum_coverage: float = DEFAULT_HISTORY_MIN_COVERAGE
    passed: bool = False
    failures: tuple[str, ...] = field(default_factory=tuple)

    def __post_init__(self) -> None:
        object.__setattr__(self, "symbol_coverage", dict(self.symbol_coverage))
        object.__setattr__(self, "failures", _unique(self.failures))

    @property
    def total_days(self) -> int:
        return self.expected_days

    @property
    def available_days(self) -> int:
        return self.aligned_days

    @property
    def is_sufficient(self) -> bool:
        return self.passed

    def to_dict(self) -> dict[str, Any]:
        return {
            "expected_days": self.expected_days,
            "aligned_days": self.aligned_days,
            "coverage_ratio": self.coverage_ratio,
            "symbol_coverage": dict(self.symbol_coverage),
            "minimum_days": self.minimum_days,
            "minimum_coverage": self.minimum_coverage,
            "passed": self.passed,
            "failures": list(self.failures),
        }


def evaluate_history_coverage(
    dated_history: Mapping[str, Mapping[str, float]],
    *,
    symbols: Sequence[str] | None = None,
    minimum_days: int = DEFAULT_HISTORY_MIN_DAYS,
    minimum_coverage: float = DEFAULT_HISTORY_MIN_COVERAGE,
) -> HistoryCoverage:
    if minimum_days < 1:
        raise ValueError("minimum_days must be at least 1")
    if not 0 <= minimum_coverage <= 1:
        raise ValueError("minimum_coverage must be between 0 and 1")
    selected = tuple(symbols or dated_history.keys())
    date_sets = [set(dated_history.get(symbol, {}).keys()) for symbol in selected]
    union_dates = set().union(*date_sets) if date_sets else set()
    aligned_dates = set.intersection(*date_sets) if date_sets else set()
    expected_days = len(union_dates)
    aligned_days = len(aligned_dates)
    coverage_ratio = aligned_days / expected_days if expected_days else 0.0
    symbol_coverage = {
        symbol: (len(dated_history.get(symbol, {})) / expected_days if expected_days else 0.0)
        for symbol in selected
    }
    failures: list[str] = []
    if aligned_days < minimum_days:
        failures.append(f"insufficient_history_days:{aligned_days}/{minimum_days}")
    if coverage_ratio < minimum_coverage:
        failures.append(f"insufficient_history_coverage:{coverage_ratio:.4f}/{minimum_coverage:.4f}")
    for symbol, ratio in symbol_coverage.items():
        if ratio < minimum_coverage:
            failures.append(f"symbol_history_coverage:{symbol}:{ratio:.4f}/{minimum_coverage:.4f}")
    return HistoryCoverage(
        expected_days=expected_days,
        aligned_days=aligned_days,
        coverage_ratio=coverage_ratio,
        symbol_coverage=symbol_coverage,
        minimum_days=minimum_days,
        minimum_coverage=minimum_coverage,
        passed=not failures,
        failures=tuple(failures),
    )


@dataclass(frozen=True)
class PortfolioHistoryPoint:
    date: str
    total_value: float
    holdings_market_value: float
    cash: float

    @property
    def value(self) -> float:
        return self.total_value

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class PortfolioValueHistory:
    points: tuple[PortfolioHistoryPoint, ...]
    coverage: HistoryCoverage
    quantities: dict[str, float]
    currency: str
    methodology: str = "current_holdings_fixed_quantity_risk_proxy"
    supports_realized_performance: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "points", tuple(self.points))
        object.__setattr__(self, "quantities", dict(self.quantities))

    @property
    def dates(self) -> tuple[str, ...]:
        return tuple(point.date for point in self.points)

    @property
    def values(self) -> tuple[float, ...]:
        return tuple(point.total_value for point in self.points)

    def to_dict(self) -> dict[str, Any]:
        return {
            "points": [point.to_dict() for point in self.points],
            "coverage": self.coverage.to_dict(),
            "quantities": dict(self.quantities),
            "currency": self.currency,
            "methodology": self.methodology,
            "supports_realized_performance": self.supports_realized_performance,
        }


PortfolioHistory = PortfolioValueHistory


def _active_quantities(context: PortfolioContext) -> dict[str, float]:
    quantities: dict[str, float] = {}
    for holding in context.holdings:
        quantity = float(_get(holding, "quantity", "qty", default=0.0) or 0.0)
        if quantity <= 0:
            continue
        symbol = str(_get(holding, "symbol", "code", default=""))
        quantities[symbol] = quantities.get(symbol, 0.0) + quantity
    return quantities


def reconstruct_portfolio_value_history(
    context: PortfolioContext,
    price_history: Mapping[str, Any] | Iterable[Any],
    *,
    minimum_days: int = DEFAULT_HISTORY_MIN_DAYS,
    minimum_coverage: float = DEFAULT_HISTORY_MIN_COVERAGE,
) -> ProviderResult[PortfolioValueHistory]:
    quantities = _active_quantities(context)
    symbols = tuple(sorted(quantities))
    normalized, parse_warnings = _normalize_dated_history(price_history, symbols)
    coverage = evaluate_history_coverage(
        normalized,
        symbols=symbols,
        minimum_days=minimum_days,
        minimum_coverage=minimum_coverage,
    )
    if not symbols:
        coverage = replace(
            coverage,
            passed=False,
            failures=_unique((*coverage.failures, "no_invested_holdings")),
        )

    common_dates = set.intersection(*(set(normalized[symbol]) for symbol in symbols)) if symbols else set()
    points: list[PortfolioHistoryPoint] = []
    for date_key in sorted(common_dates):
        holdings_value = sum(quantities[symbol] * normalized[symbol][date_key] for symbol in symbols)
        points.append(
            PortfolioHistoryPoint(
                date=date_key,
                total_value=holdings_value + context.cash,
                holdings_market_value=holdings_value,
                cash=context.cash,
            )
        )
    history = PortfolioValueHistory(
        points=tuple(points),
        coverage=coverage,
        quantities=quantities,
        currency=context.currency,
    )
    source_meta = context.meta or _default_meta(context.currency, source="portfolio_price_history")
    diagnostics = _unique((*parse_warnings, *coverage.failures))
    result_meta = _meta_with_diagnostics(
        source_meta,
        warnings=diagnostics,
        quality_flags=("fixed_current_quantities",) + (() if coverage.passed else ("insufficient_history",)),
        error_code=None if coverage.passed else "insufficient_history_coverage",
    )
    return ProviderResult(
        data=history,
        meta=result_meta,
        status="ready" if coverage.passed else "error",
        warnings=parse_warnings,
        errors=() if coverage.passed else coverage.failures,
    )


reconstruct_portfolio_history = reconstruct_portfolio_value_history
reconstruct_fixed_quantity_history = reconstruct_portfolio_value_history


@dataclass(frozen=True)
class RiskContribution:
    symbol: str
    weight: float
    marginal_variance: float
    marginal_volatility: float
    component_variance: float
    component_volatility: float
    annualized_component_volatility: float
    contribution_pct: float

    @property
    def risk_contribution(self) -> float:
        return self.component_volatility

    @property
    def risk_contribution_pct(self) -> float:
        return self.contribution_pct

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class RiskContributionResult:
    contributions: tuple[RiskContribution, ...]
    covariance_matrix: dict[str, dict[str, float]]
    portfolio_variance: float
    portfolio_volatility: float
    annualized_volatility: float
    aligned_dates: tuple[str, ...]
    observations: int
    coverage: HistoryCoverage
    periods_per_year: int = 252

    def __post_init__(self) -> None:
        object.__setattr__(self, "contributions", tuple(self.contributions))
        object.__setattr__(
            self,
            "covariance_matrix",
            {symbol: dict(row) for symbol, row in self.covariance_matrix.items()},
        )
        object.__setattr__(self, "aligned_dates", tuple(self.aligned_dates))

    @property
    def contribution_by_symbol(self) -> dict[str, float]:
        return {row.symbol: row.contribution_pct for row in self.contributions}

    @property
    def rows(self) -> tuple[RiskContribution, ...]:
        return self.contributions

    def to_dict(self) -> dict[str, Any]:
        return {
            "contributions": [row.to_dict() for row in self.contributions],
            "covariance_matrix": {symbol: dict(row) for symbol, row in self.covariance_matrix.items()},
            "portfolio_variance": self.portfolio_variance,
            "portfolio_volatility": self.portfolio_volatility,
            "annualized_volatility": self.annualized_volatility,
            "aligned_dates": list(self.aligned_dates),
            "observations": self.observations,
            "coverage": self.coverage.to_dict(),
            "periods_per_year": self.periods_per_year,
        }


def _normalize_return_history(
    return_history: Mapping[str, Any],
    symbols: Sequence[str],
) -> dict[str, dict[str, float]]:
    result: dict[str, dict[str, float]] = {symbol: {} for symbol in symbols}
    normalized_keys = {_normalize_symbol(key): key for key in return_history}
    for symbol in symbols:
        raw_key = normalized_keys.get(_normalize_symbol(symbol))
        raw_series = return_history.get(raw_key) if raw_key is not None else None
        for raw_date, raw_value in _series_rows(raw_series):
            date_key = _normalize_date(raw_date)
            value = _finite(raw_value)
            if date_key is not None and value is not None:
                result[symbol][date_key] = value
    return result


def calculate_date_aligned_covariance_risk_contributions(
    weights: Mapping[str, Any],
    return_history: Mapping[str, Any],
    *,
    periods_per_year: int = 252,
    minimum_observations: int = 2,
    minimum_coverage: float = 0.0,
) -> RiskContributionResult:
    """Calculate Euler volatility contributions from returns sharing the same dates."""
    if periods_per_year <= 0:
        raise ValueError("periods_per_year must be positive")
    clean_weights: dict[str, float] = {}
    for raw_symbol, raw_weight in weights.items():
        symbol = str(raw_symbol)
        weight = _finite(raw_weight)
        if weight is None or weight < 0:
            raise ValueError(f"invalid weight for {symbol}")
        if weight > 0:
            clean_weights[symbol] = weight
    if not clean_weights:
        raise ValueError("at least one positive weight is required")

    symbols = tuple(sorted(clean_weights))
    normalized = _normalize_return_history(return_history, symbols)
    coverage = evaluate_history_coverage(
        normalized,
        symbols=symbols,
        minimum_days=minimum_observations,
        minimum_coverage=minimum_coverage,
    )
    if not coverage.passed:
        raise ValueError("; ".join(coverage.failures))
    aligned_dates = tuple(sorted(set.intersection(*(set(normalized[symbol]) for symbol in symbols))))
    observations = len(aligned_dates)
    values = {symbol: [normalized[symbol][date_key] for date_key in aligned_dates] for symbol in symbols}
    means = {symbol: sum(series) / observations for symbol, series in values.items()}
    denominator = observations - 1
    covariance_matrix: dict[str, dict[str, float]] = {symbol: {} for symbol in symbols}
    for left in symbols:
        for right in symbols:
            covariance = sum(
                (values[left][index] - means[left]) * (values[right][index] - means[right])
                for index in range(observations)
            ) / denominator
            covariance_matrix[left][right] = covariance

    marginal_variances = {
        symbol: sum(covariance_matrix[symbol][other] * clean_weights[other] for other in symbols)
        for symbol in symbols
    }
    component_variances = {
        symbol: clean_weights[symbol] * marginal_variances[symbol] for symbol in symbols
    }
    portfolio_variance = sum(component_variances.values())
    if portfolio_variance < 0 and math.isclose(portfolio_variance, 0.0, abs_tol=1e-15):
        portfolio_variance = 0.0
    if portfolio_variance < 0:
        raise ValueError("covariance matrix produced negative portfolio variance")
    portfolio_volatility = math.sqrt(portfolio_variance)
    annualization = math.sqrt(periods_per_year)
    rows: list[RiskContribution] = []
    for symbol in symbols:
        marginal_volatility = (
            marginal_variances[symbol] / portfolio_volatility if portfolio_volatility > 0 else 0.0
        )
        component_volatility = clean_weights[symbol] * marginal_volatility
        contribution_pct = (
            component_variances[symbol] / portfolio_variance if portfolio_variance > 0 else 0.0
        )
        rows.append(
            RiskContribution(
                symbol=symbol,
                weight=clean_weights[symbol],
                marginal_variance=marginal_variances[symbol],
                marginal_volatility=marginal_volatility,
                component_variance=component_variances[symbol],
                component_volatility=component_volatility,
                annualized_component_volatility=component_volatility * annualization,
                contribution_pct=contribution_pct,
            )
        )
    return RiskContributionResult(
        contributions=tuple(rows),
        covariance_matrix=covariance_matrix,
        portfolio_variance=portfolio_variance,
        portfolio_volatility=portfolio_volatility,
        annualized_volatility=portfolio_volatility * annualization,
        aligned_dates=aligned_dates,
        observations=observations,
        coverage=coverage,
        periods_per_year=periods_per_year,
    )


calculate_covariance_risk_contributions = calculate_date_aligned_covariance_risk_contributions


def _current_symbol_values(context: PortfolioContext) -> dict[str, float]:
    values: dict[str, float] = {}
    for holding in context.holdings:
        symbol = str(_get(holding, "symbol", "code", default=""))
        value = _holding_market_value(holding)
        if value > 0:
            values[symbol] = values.get(symbol, 0.0) + value
    return values


def calculate_portfolio_risk_contributions(
    context: PortfolioContext,
    price_history: Mapping[str, Any] | Iterable[Any],
    *,
    minimum_days: int = DEFAULT_HISTORY_MIN_DAYS,
    minimum_coverage: float = DEFAULT_HISTORY_MIN_COVERAGE,
    periods_per_year: int = 252,
) -> ProviderResult[RiskContributionResult]:
    history_result = reconstruct_portfolio_value_history(
        context,
        price_history,
        minimum_days=minimum_days,
        minimum_coverage=minimum_coverage,
    )
    if history_result.data is None or not history_result.data.coverage.passed:
        return ProviderResult(
            data=None,
            meta=history_result.meta,
            status="error",
            warnings=history_result.warnings,
            errors=history_result.errors or ("insufficient_history_coverage",),
        )

    values = _current_symbol_values(context)
    if context.computed_total <= 0 or not values:
        result_meta = _meta_with_diagnostics(
            history_result.meta,
            quality_flags=("risk_calculation_blocked",),
            error_code="portfolio_value_not_positive",
        )
        return ProviderResult(
            data=None,
            meta=result_meta,
            status="error",
            errors=("portfolio_value_not_positive",),
        )
    weights = {symbol: value / context.computed_total for symbol, value in values.items()}
    normalized, parse_warnings = _normalize_dated_history(price_history, tuple(sorted(values)))
    common_dates = tuple(sorted(set.intersection(*(set(normalized[symbol]) for symbol in sorted(values)))))
    returns: dict[str, dict[str, float]] = {symbol: {} for symbol in values}
    for previous_date, current_date in zip(common_dates, common_dates[1:]):
        for symbol in values:
            previous_price = normalized[symbol][previous_date]
            current_price = normalized[symbol][current_date]
            returns[symbol][current_date] = current_price / previous_price - 1.0

    try:
        risk = calculate_date_aligned_covariance_risk_contributions(
            weights,
            returns,
            periods_per_year=periods_per_year,
            minimum_observations=2,
            minimum_coverage=1.0,
        )
    except ValueError as exc:
        result_meta = _meta_with_diagnostics(
            history_result.meta,
            warnings=parse_warnings,
            quality_flags=("risk_calculation_failed",),
            error_code="covariance_risk_calculation_failed",
        )
        return ProviderResult(
            data=None,
            meta=result_meta,
            status="error",
            warnings=parse_warnings,
            errors=(str(exc),),
        )
    risk = replace(risk, coverage=history_result.data.coverage)
    result_meta = _meta_with_diagnostics(
        history_result.meta,
        warnings=parse_warnings,
        quality_flags=("date_aligned_covariance", "current_market_value_weights"),
        error_code=None,
    )
    return ProviderResult(data=risk, meta=result_meta, warnings=parse_warnings)


calculate_portfolio_covariance_risk_contributions = calculate_portfolio_risk_contributions


__all__ = [
    "DEFAULT_HISTORY_MIN_COVERAGE",
    "DEFAULT_HISTORY_MIN_DAYS",
    "HistoryCoverage",
    "PortfolioContext",
    "PortfolioContextValidationError",
    "PortfolioHistory",
    "PortfolioHistoryPoint",
    "PortfolioValidationIssue",
    "PortfolioValueHistory",
    "RiskContribution",
    "RiskContributionResult",
    "adapt_legacy_csv_rows",
    "build_portfolio_context",
    "calculate_covariance_risk_contributions",
    "calculate_date_aligned_covariance_risk_contributions",
    "calculate_portfolio_covariance_risk_contributions",
    "calculate_portfolio_risk_contributions",
    "evaluate_history_coverage",
    "legacy_csv_rows_to_context",
    "parse_legacy_portfolio_csv",
    "portfolio_context_from_legacy_rows",
    "reconstruct_fixed_quantity_history",
    "reconstruct_portfolio_history",
    "reconstruct_portfolio_value_history",
    "validate_portfolio_context",
]
