from __future__ import annotations

import csv
from datetime import datetime
import io
from zoneinfo import ZoneInfo

import streamlit as st

from .backtest import simulate_long_trade, summarize_backtest
from .compounding import CompoundingAssumptions, analyze_compounding
from .config import KRAlphaConfig
from .factors import factor_spec
from .fixtures import FixtureKRAlphaProvider
from .risk import LiveInterlockInput, evaluate_kill_switch, evaluate_live_interlocks
from .service import KRAlphaOverview, build_overview


KST = ZoneInfo("Asia/Seoul")
RATING_KO = {
    "WATCH": "관찰",
    "HIGH_RISK_EXCLUDE": "고위험 제외",
}


def _fixture_decision_time() -> datetime:
    return datetime(2026, 6, 18, 16, 0, tzinfo=KST)


def _candidate_rows(overview: KRAlphaOverview) -> list[dict[str, object]]:
    return [
        {
            "순위": rank,
            "종목": f"{candidate.name_ko} ({candidate.ticker})",
            "시장": candidate.market,
            "업종": candidate.sector,
            "알파 점수": candidate.composite_score,
            "비용 후 기대수익": "검증 대기" if candidate.expected_net_return is None else f"{candidate.expected_net_return:+.2%}",
            "신뢰도": f"{candidate.confidence * 100:.0f}/100",
            "예상 비용": f"{candidate.cost_estimate_bps:.1f}bp",
            "용량": f"{candidate.capacity_krw:,.0f}원",
            "최대 검토 비중": f"{candidate.suggested_max_weight * 100:.1f}%",
            "판정": RATING_KO.get(candidate.rating, candidate.rating),
            "위험": ", ".join(candidate.risk_flags) or "특이사항 없음",
            "데이터": overview.data_badge,
        }
        for rank, candidate in enumerate(overview.candidates, start=1)
    ]


def _csv_bytes(rows: list[dict[str, object]]) -> bytes:
    if not rows:
        return b""
    buffer = io.StringIO()
    writer = csv.DictWriter(buffer, fieldnames=list(rows[0]))
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode("utf-8-sig")


def _render_overview(overview: KRAlphaOverview) -> None:
    metrics = st.columns(4)
    metrics[0].metric("데이터 모드", overview.data_mode.upper())
    metrics[1].metric("모델 상태", overview.model_status)
    metrics[2].metric("후보 수", str(len(overview.candidates)))
    metrics[3].metric("투자판단 적격", str(sum(candidate.investment_eligible for candidate in overview.candidates)))
    st.caption(
        f"시장 국면: {overview.regime.label} · 점수 {overview.regime.score:+.2f} · "
        f"목표 포트폴리오: {overview.target_portfolio.status} · 현금 {overview.target_portfolio.cash_weight:.1%}"
    )
    for warning in overview.warnings:
        st.warning(warning)
    st.caption(
        f"기준시각: {overview.decision_time.astimezone(KST).strftime('%Y.%m.%d %H:%M')} · "
        f"공급자: {overview.provider} {overview.provider_version} · 설정 해시: {overview.config_hash}"
    )
    rows = _candidate_rows(overview)
    if not rows:
        st.info("연결된 데이터 공급자가 없어 KR Alpha 계산을 수행하지 않았습니다.")
        return
    st.dataframe(rows, hide_index=True, use_container_width=True)
    st.download_button(
        "후보 목록 CSV 다운로드",
        data=_csv_bytes(rows),
        file_name="kr_alpha_fixture_candidates.csv",
        mime="text/csv",
        use_container_width=True,
    )
    labels = {candidate.instrument_id: f"{candidate.name_ko} ({candidate.ticker})" for candidate in overview.candidates}
    selected_id = st.selectbox("팩터 근거 확인", tuple(labels), format_func=lambda value: labels[value])
    selected = next(candidate for candidate in overview.candidates if candidate.instrument_id == selected_id)
    factor_rows = []
    for value in selected.factor_values:
        spec = factor_spec(value.factor_name)
        factor_rows.append(
            {
                "팩터": spec.label_ko,
                "원시값": "데이터 부족" if value.raw_value is None else f"{value.raw_value:.3f}",
                "강도(z)": "계산 불가" if value.z_score is None else f"{value.z_score:+.2f}",
                "백분위": "계산 불가" if value.percentile is None else f"{value.percentile * 100:.0f}%",
                "보유기간": f"{spec.holding_days}거래일",
                "비용 민감도": spec.cost_sensitivity,
                "기준시각": value.available_at.astimezone(KST).strftime("%Y.%m.%d %H:%M"),
            }
        )
    st.dataframe(factor_rows, hide_index=True, use_container_width=True)


def _render_backtest(config: KRAlphaConfig, overview: KRAlphaOverview) -> None:
    st.subheader("비용 포함 fixture 백테스트")
    if config.data_mode != "fixture":
        st.info("paper/live 역사 데이터 어댑터가 연결되지 않아 백테스트를 실행하지 않습니다.")
        return
    provider = FixtureKRAlphaProvider()
    stocks = provider.snapshot(overview.decision_time)
    trades = tuple(simulate_long_trade(stock, overview.decision_time, config) for stock in stocks)
    summary = summarize_backtest(trades)
    st.warning("FIXTURE ONLY · 연구 파이프라인 검증용이며 실전 성과가 아닙니다.")
    metrics = st.columns(4)
    metrics[0].metric("비용 전 수익", "계산 불가" if summary.gross_return is None else f"{summary.gross_return:+.2%}")
    metrics[1].metric("비용 후 수익", "계산 불가" if summary.net_return is None else f"{summary.net_return:+.2%}")
    metrics[2].metric("평균 비용", f"{summary.total_cost_bps:.1f}bp")
    metrics[3].metric("방법론", summary.methodology)
    st.dataframe(
        [
            {
                "종목 ID": trade.instrument_id,
                "상태": trade.status,
                "진입": "불가" if trade.entry_time is None else trade.entry_time.strftime("%Y.%m.%d %H:%M"),
                "체결률": f"{trade.fill_ratio * 100:.0f}%",
                "비용 전": "계산 불가" if trade.gross_return is None else f"{trade.gross_return:+.2%}",
                "비용 후": "계산 불가" if trade.net_return is None else f"{trade.net_return:+.2%}",
                "근거": ", ".join(trade.reason_codes) or "정상 체결",
            }
            for trade in trades
        ],
        hide_index=True,
        use_container_width=True,
    )


def _render_compounding(config: KRAlphaConfig) -> None:
    st.subheader("극단 복리 목표 분석기")
    left, middle, right = st.columns(3)
    initial = left.number_input("초기 자본", min_value=1.0, value=10_000_000.0, step=1_000_000.0)
    target = middle.number_input("목표 자본", min_value=1.0, value=100_000_000.0, step=10_000_000.0)
    months = right.number_input("기간(개월)", min_value=1, max_value=240, value=36, step=1)
    expected = left.number_input("가정 월수익률(%)", min_value=-100.0, max_value=500.0, value=2.0, step=0.5) / 100.0
    volatility = middle.number_input("월 변동성(%)", min_value=0.0, max_value=500.0, value=8.0, step=0.5) / 100.0
    leverage = right.number_input("레버리지", min_value=0.0, max_value=5.0, value=1.0, step=0.1)
    result = analyze_compounding(
        CompoundingAssumptions(
            initial_capital=initial,
            target_capital=target,
            months=int(months),
            expected_monthly_return=expected,
            monthly_volatility=volatility,
            leverage=leverage,
            monthly_cost=config.transaction_costs.base_round_trip_bps / 10_000.0,
            seed=config.fixture_seed,
        )
    )
    metrics = st.columns(4)
    metrics[0].metric("필요 월복리", f"{result.required_monthly_return * 100:.2f}%")
    metrics[1].metric("연복리 환산", f"{result.required_annual_return * 100:,.1f}%")
    metrics[2].metric("목표 달성 확률", f"{result.target_probability * 100:.1f}%")
    metrics[3].metric("가능성 등급", result.feasibility_grade)
    st.caption(f"seed {result.seed} · 추정 MDD {result.expected_max_drawdown:.1%} · 손실한도 도달 {result.drawdown_limit_probability:.1%}")
    st.dataframe(
        [{"종료자산 백분위": f"{level}%", "금액": f"{amount:,.0f}원"} for level, amount in result.terminal_percentiles.items()],
        hide_index=True,
        use_container_width=True,
    )
    for warning in result.warnings:
        st.warning(warning)


def _render_model_health(config: KRAlphaConfig, overview: KRAlphaOverview) -> None:
    st.subheader("모델·리스크 상태")
    kill = evaluate_kill_switch(config, daily_return=0.0, weekly_return=0.0, drawdown=0.0)
    live = evaluate_live_interlocks(
        LiveInterlockInput(False, False, False, False, False, False, False, False, kill.status == "CLEAR", False, False)
    )
    st.info("OOS 성과 표본이 없어 모델 상태는 INSUFFICIENT_EVIDENCE입니다. 팩터 prior는 자동 승격되지 않습니다.")
    st.metric("킬스위치", kill.status)
    st.metric("실거래 상태", "차단")
    st.caption("차단 사유: " + ", ".join(live.blocking_reasons))
    st.dataframe(
        [
            {
                "팩터": factor_spec(name).label_ko,
                "현재 비중": f"{weight * 100:.1f}%",
                "상태": overview.governance.statuses[name],
                "Rolling OOS IC": "표본 부족",
            }
            for name, weight in overview.governance.weights.items()
        ],
        hide_index=True,
        use_container_width=True,
    )


def render_kr_alpha_section(config: KRAlphaConfig) -> None:
    st.title("KR Alpha 연구실")
    st.caption("한국시장 PIT 팩터·비용·리스크를 검증하는 연구 화면입니다. 자동 주문은 지원하지 않습니다.")
    decision_time = _fixture_decision_time() if config.data_mode == "fixture" else datetime.now(KST)
    overview = build_overview(decision_time, config)
    tabs = st.tabs(["개요·후보", "비용 포함 백테스트", "극단 복리 분석", "모델·리스크"])
    with tabs[0]:
        _render_overview(overview)
    with tabs[1]:
        _render_backtest(config, overview)
    with tabs[2]:
        _render_compounding(config)
    with tabs[3]:
        _render_model_health(config, overview)
