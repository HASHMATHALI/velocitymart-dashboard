import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# -------------------------------------------------
# App Configuration
# -------------------------------------------------
st.set_page_config(
    page_title="VelocityMart Warehouse Dashboard",
    layout="wide"
)

st.title("📦 VelocityMart – Warehouse Monitoring Dashboard")

BASE_DIR = Path(__file__).parent


# -------------------------------------------------
# Load Data
# -------------------------------------------------
@st.cache_data
def load_data():
    try:
        sku_master = pd.read_csv(BASE_DIR / "sku_master_converted.xlsx.csv")
        orders = pd.read_csv(BASE_DIR / "order_transactions_converted.xlsx.csv")
        warehouse = pd.read_csv(BASE_DIR / "warehouse_constraints_converted.xlsx.csv")
    except Exception as e:
        st.error(f"❌ File load error: {e}")
        st.stop()

    # Required columns check
    if not {"sku_id", "current_slot", "temp_req"}.issubset(sku_master.columns):
        st.error("❌ sku_master file missing required columns")
        st.stop()

    if not {"slot_id", "temp_zone"}.issubset(warehouse.columns):
        st.error("❌ warehouse_constraints file missing required columns")
        st.stop()

    # Merge warehouse temperature zones
    df = sku_master.merge(
        warehouse[["slot_id", "temp_zone"]],
        left_on="current_slot",
        right_on="slot_id",
        how="left"
    )

    df.rename(
        columns={
            "temp_req": "required_temp",
            "temp_zone": "current_zone"
        },
        inplace=True
    )

    # Weekly picks
    weekly_picks = orders.groupby("sku_id").size()
    df["weekly_picks"] = df["sku_id"].map(weekly_picks).fillna(0)

    # Risk score
    df["days_at_risk"] = 3
    df["priority_score"] = df["weekly_picks"] * df["days_at_risk"]

    return df


# -------------------------------------------------
# Sidebar Navigation
# -------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Warehouse Health Overview", "Temperature Compliance"]
)

data = load_data()


# =================================================
# PAGE 1: WAREHOUSE HEALTH OVERVIEW
# =================================================
if page == "Warehouse Health Overview":

    st.subheader("🏭 Warehouse Health Overview")

    total_skus = len(data)
    temp_mismatches = (data["required_temp"] != data["current_zone"]).sum()
    high_risk = (data["priority_score"] > data["priority_score"].median()).sum()

    col1, col2, col3 = st.columns(3)

    col1.metric("Total SKUs", total_skus)
    col2.metric("Temperature Mismatches", temp_mismatches)
    col3.metric("High-Risk SKUs", high_risk)

    st.markdown("---")

    st.markdown("### 🔥 Top High-Risk SKUs")

    top_risk = data.sort_values("priority_score", ascending=False).head(15)

    fig = px.bar(
        top_risk,
        x="sku_id",
        y="priority_score",
        color="priority_score",
        color_continuous_scale="Reds",
        title="Top 15 High-Risk SKUs"
    )

    fig.update_layout(
        xaxis_title="SKU ID",
        yaxis_title="Risk Score",
        plot_bgcolor="rgba(0,0,0,0)"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📋 Risk Breakdown Table")
    st.dataframe(
        data.sort_values("priority_score", ascending=False),
        use_container_width=True
    )


# =================================================
# PAGE 2: TEMPERATURE COMPLIANCE (FIXED)
# =================================================
elif page == "Temperature Compliance":

    st.subheader("🌡 Temperature Compliance Analysis")

    compliance_df = data.copy()
    compliance_df["status"] = compliance_df.apply(
        lambda x: "Compliant" if x["required_temp"] == x["current_zone"] else "Violation",
        axis=1
    )

    # -------- BAR CHART (PROFESSIONAL) --------
    status_counts = (
        compliance_df["status"]
        .value_counts()
        .reindex(["Compliant", "Violation"], fill_value=0)
        .reset_index()
    )

    status_counts.columns = ["Status", "Count"]

    fig = px.bar(
        status_counts,
        x="Status",
        y="Count",
        text="Count",
        color="Status",
        color_discrete_map={
            "Compliant": "#2ecc71",
            "Violation": "#e74c3c"
        },
        title="Temperature Compliance Status"
    )

    fig.update_traces(textposition="outside")

    fig.update_layout(
        yaxis_title="Number of SKUs",
        xaxis_title="Status",
        yaxis=dict(range=[0, max(5, status_counts["Count"].max() + 5)]),
        plot_bgcolor="rgba(0,0,0,0)"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ❌ SKUs with Temperature Violations")

    st.dataframe(
        compliance_df[compliance_df["status"] == "Violation"],
        use_container_width=True
    )

    # Download report
    csv = compliance_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇ Download Compliance Report",
        csv,
        "temperature_compliance_report.csv",
        "text/csv"
    )


# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown("---")
st.caption("VelocityMart Warehouse Dashboard | Built with Streamlit 🚀")

