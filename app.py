"""SlotSense - compliance-first re-slotting for the VelocityMart warehouse."""
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

import engine

AMBER, CYAN, RED, INK, PAPER, GRID = "#FFB000", "#5CE1E6", "#FF5A5F", "#0B1626", "#E8EEF7", "#1C2D47"

st.set_page_config(page_title="SlotSense · VelocityMart", page_icon="▦", layout="wide")

st.markdown(
    f"""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=Space+Grotesk:wght@400;500;700&display=swap');
html, body, [class*="css"], .stMarkdown p {{ font-family: 'Space Grotesk', sans-serif; }}
/* blueprint paper: faint engineering grid behind everything */
.stApp {{
  background-color: {INK};
  background-image: linear-gradient({GRID}55 1px, transparent 1px), linear-gradient(90deg, {GRID}55 1px, transparent 1px);
  background-size: 32px 32px;
}}
h1, h2, h3, [data-testid="stMetricLabel"], .mono {{ font-family: 'IBM Plex Mono', monospace !important; letter-spacing: .02em; }}
.masthead {{ display:flex; align-items:baseline; gap:16px; border-bottom:1px dashed {AMBER}; padding-bottom:10px; margin-bottom:6px; }}
.masthead .mark {{ font-family:'IBM Plex Mono',monospace; font-weight:600; font-size:2rem; color:{PAPER}; }}
.masthead .mark b {{ color:{AMBER}; }}
.masthead .sub {{ color:#8FA3BF; font-size:.9rem; }}
[data-testid="stMetric"] {{ border:1px solid {GRID}; border-left:3px solid {CYAN}; background:{INK}CC; padding:12px 14px; border-radius:2px; }}
.chip {{ display:inline-block; font-family:'IBM Plex Mono',monospace; font-size:.72rem; padding:2px 8px; margin:2px 4px 2px 0;
        border:1px solid {AMBER}; color:{AMBER}; border-radius:2px; }}
.note {{ border-left:3px solid {AMBER}; padding:8px 14px; background:{AMBER}14; color:{PAPER}; font-size:.9rem; margin:8px 0 16px; }}
.stTabs [data-baseweb="tab"] {{ font-family:'IBM Plex Mono',monospace; text-transform:uppercase; font-size:.8rem; }}
</style>
<div class="masthead">
  <span class="mark">SLOT<b>SENSE</b></span>
  <span class="sub">VelocityMart floor intelligence · every pick from a wrong slot is a risk you can schedule away</span>
</div>
""",
    unsafe_allow_html=True,
)


@st.cache_data(show_spinner="Reading the floor plan…")
def get_warehouse() -> engine.Warehouse:
    return engine.load()


@st.cache_data(show_spinner="Planning moves…")
def get_plan() -> pd.DataFrame:
    return engine.plan_moves(get_warehouse())


def layout(fig: go.Figure, height: int = 360) -> go.Figure:
    fig.update_layout(
        height=height, margin=dict(l=10, r=10, t=30, b=10), paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
        font=dict(family="IBM Plex Mono, monospace", color=PAPER, size=11),
    )
    return fig


wh = get_warehouse()
full_plan = get_plan()
summary = engine.issue_summary(wh)

c1, c2, c3, c4 = st.columns(4)
c1.metric("Slot compliance", f"{engine.compliance_rate(wh.skus):.0%}", help="SKUs whose current slot breaks no rule")
c2.metric("SKUs in a bad slot", f"{int((wh.skus.issue_count > 0).sum())} / {len(wh.skus)}")
c3.metric("Risky picks per week", f"{wh.skus.loc[wh.skus.issue_count > 0, 'picks_per_week'].sum():,.0f}")
c4.metric("Slots in use", f"{wh.skus.current_slot.nunique():,} / {len(wh.slots):,}")

tab_floor, tab_plan, tab_ledger, tab_shift, tab_pickers = st.tabs(
    ["Floor map", "Move planner", "Risk ledger", "Shift pressure", "Picker signals"]
)

# ------------------------------------------------------------------ floor map
with tab_floor:
    left, right = st.columns([3, 1])
    metric_label = right.radio(
        "Colour the floor by",
        ["Risk exposure", "Rule breaks", "Pick velocity", "Occupancy"],
        help="Exposure = severity of the broken rules x picks per week",
    )
    metric = {"Risk exposure": "exposure", "Rule breaks": "issue_count", "Pick velocity": "picks_per_week", "Occupancy": "sku_id"}[metric_label]
    grid = engine.floor_grid(wh, metric)
    fig = go.Figure(
        go.Heatmap(
            z=grid.values, x=grid.columns, y=[f"Level {lvl}" for lvl in grid.index],
            colorscale=[[0, INK], [0.02, GRID], [0.5, AMBER], [1, RED]] if metric != "picks_per_week" else [[0, INK], [0.02, GRID], [1, CYAN]],
            hovertemplate="Aisle %{x} · %{y}<br>" + metric_label + ": %{z:.1f}<extra></extra>", xgap=1, ygap=2,
        )
    )
    fig.update_xaxes(tickangle=90, tickfont=dict(size=8), showgrid=False)
    fig.update_yaxes(showgrid=False)
    left.plotly_chart(layout(fig, 380), width="stretch")
    left.caption("Side elevation of the building: aisles left to right, shelf level A (floor) at the bottom to F (top).")

    right.markdown("**What is wrong, by rule**")
    for row in summary.itertuples():
        right.markdown(f"<span class='chip'>{row.skus}</span> {row.issue}", unsafe_allow_html=True)

# --------------------------------------------------------------- move planner
with tab_plan:
    st.markdown(
        "<div class='note'>Re-slotting everything at once stops the floor. Pick how many moves a shift can absorb; "
        "the plan always spends them on the SKUs that are handled most often while breaking the most serious rules.</div>",
        unsafe_allow_html=True,
    )
    if full_plan.empty:
        st.success("No moves needed: every SKU is in a compliant slot.")
    else:
        budget = st.slider("Moves in this work order", 1, len(full_plan), min(25, len(full_plan)))
        plan = full_plan.head(budget)
        after = engine.apply_moves(wh, plan)
        before_exp, after_exp = wh.skus.exposure.sum(), after.skus.exposure.sum()

        m1, m2, m3 = st.columns(3)
        m1.metric("Compliance after", f"{engine.compliance_rate(after.skus):.0%}",
                  f"{(engine.compliance_rate(after.skus) - engine.compliance_rate(wh.skus)) * 100:+.1f} pts")
        m2.metric("Risk exposure removed", f"{(1 - after_exp / before_exp):.0%}" if before_exp else "n/a")
        m3.metric("Fully fixable SKUs", f"{len(full_plan)}", help="SKUs for which a slot satisfying every rule exists")

        # Diminishing returns: cumulative exposure removed as the budget grows.
        curve = full_plan.exposure_removed.cumsum() / before_exp * 100
        fig = go.Figure(go.Scatter(x=list(range(1, len(curve) + 1)), y=curve, mode="lines", line=dict(color=CYAN, width=2), fill="tozeroy", fillcolor=CYAN + "22"))
        fig.add_vline(x=budget, line=dict(color=AMBER, dash="dash"))
        fig.update_xaxes(title="moves made", gridcolor=GRID)
        fig.update_yaxes(title="% of exposure removed", gridcolor=GRID)
        st.plotly_chart(layout(fig, 260), width="stretch")

        st.dataframe(plan, width="stretch", hide_index=True)
        st.download_button("Download work order (CSV)", plan.to_csv(index=False), "slotsense_work_order.csv", "text/csv")

# ---------------------------------------------------------------- risk ledger
with tab_ledger:
    f1, f2 = st.columns([2, 1])
    chosen = f1.multiselect("Rules", list(engine.ISSUES.values()), default=list(engine.ISSUES.values()))
    category = f2.selectbox("Category", ["All"] + sorted(wh.skus.category.unique()))
    keys = [k for k, v in engine.ISSUES.items() if v in chosen]
    ledger = wh.skus[wh.skus[keys].any(axis=1)] if keys else wh.skus.iloc[0:0]
    if category != "All":
        ledger = ledger[ledger.category == category]
    ledger = ledger.sort_values("exposure", ascending=False)
    view = ledger[["sku_id", "category", "current_slot", "temp_req", "temp_zone", "weight_kg", "max_weight_kg", "picks_per_week", "exposure"]].copy()
    view.insert(3, "broken rules", ledger.issues.str.join(" · "))
    st.caption(f"{len(view)} SKUs, worst first.")
    st.dataframe(view.round({"picks_per_week": 1, "exposure": 1}), width="stretch", hide_index=True)

# ------------------------------------------------------------- shift pressure
with tab_shift:
    pressure = engine.shift_pressure(wh)
    fig = go.Figure(go.Heatmap(z=pressure.values, x=[f"{h:02d}:00" for h in pressure.columns], y=pressure.index,
                               colorscale=[[0, INK], [1, CYAN]], hovertemplate="%{y} %{x}<br>%{z:.0f} picks/hour<extra></extra>", xgap=2, ygap=2))
    st.plotly_chart(layout(fig, 300), width="stretch")
    peak_day, peak_hour = pressure.stack().idxmax()
    st.markdown(f"<div class='note'>Peak is <b>{peak_day} {peak_hour:02d}:00</b> at about <b>{pressure.loc[peak_day, peak_hour]:.0f} picks/hour</b>. "
                "Schedule re-slotting moves outside the coloured band.</div>", unsafe_allow_html=True)

    st.markdown("**Narrow aisles under peak load** (1.2 m: two pickers cannot pass)")
    narrow = engine.narrow_aisle_pressure(wh)
    if narrow.empty:
        st.caption("No picks land in narrow aisles during peak hours.")
    else:
        fig = go.Figure(go.Bar(x=narrow.aisle_id, y=narrow.picks_per_peak_hour, marker_color=AMBER))
        fig.update_yaxes(title="picks per peak hour", gridcolor=GRID)
        st.plotly_chart(layout(fig, 240), width="stretch")

# ------------------------------------------------------------- picker signals
with tab_pickers:
    pickers = engine.picker_anomalies(wh)
    fig = go.Figure(go.Bar(x=pickers.picker_id, y=pickers.avg_travel_m, marker_color=[RED if f else CYAN for f in pickers.flag]))
    fig.update_yaxes(title="avg logged travel per pick (m)", gridcolor=GRID)
    st.plotly_chart(layout(fig, 280), width="stretch")
    flagged = pickers[pickers.flag]
    if flagged.empty:
        st.caption("No picker deviates from the team by more than 3.5 robust standard deviations.")
    for row in flagged.itertuples():
        st.markdown(
            f"<div class='note'><b>{row.picker_id}</b> logs {row.avg_travel_m} m per pick against a team median of "
            f"{pickers.avg_travel_m.median():.1f} m (robust z = {row.z}). With a similar pick count, that points to a "
            "scanner or route-logging fault before it points to a faster picker. Worth a look.</div>",
            unsafe_allow_html=True,
        )
    st.dataframe(pickers, width="stretch", hide_index=True)

st.caption(f"Based on {len(wh.orders):,} picks over {wh.weeks:.0f} weeks · {len(wh.skus)} SKUs · {len(wh.slots):,} slots")
