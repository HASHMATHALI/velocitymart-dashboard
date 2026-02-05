import streamlit as st
import pandas as pd
import plotly.express as px
from pathlib import Path

# -------------------------------------------------
# App Config
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

    # Validate columns
    if not {"sku_id", "current_slot", "temp_req"}.issubset(sku_master.columns):
        st.error("❌ sku_master missing required columns")
        st.stop()

    if not {"slot_id", "temp_zone"}.issubset(warehouse.columns):
        st.error("❌ warehouse_constraints missing required columns")
        st.stop()

    # Merge temperature zones
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

    # Risk scoring
    df["days_at_risk"] = 3
    df["priority_score"] = df["weekly_picks"] * df["days_at_risk"]

    # Compliance flag
    df["status"] = df.apply(
        lambda x: "Compliant" if x["required_temp"] == x["current_zone"] else "Violation",
        axis=1
    )

    return df


data = load_data()

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Warehouse Health Overview", "Temperature Compliance"]
)

# =================================================
# PAGE 1: WAREHOUSE HEALTH OVERVIEW (FIXED)
# =================================================
if page == "Warehouse Health Overview":

    st.subheader("🏭 Warehouse Health Overview")

    total_skus = len(data)
    violations = (data["status"] == "Violation").sum()
    compliant = (data["status"] == "Compliant").sum()
    high_risk = (data["priority_score"] > data["priority_score"].median()).sum()

    col1, col2, col3, col4 = st.columns(4)

    col1.metric("Total SKUs", total_skus)
    col2.metric("Compliant SKUs", compliant)
    col3.metric("Violations", violations)
    col4.metric("High-Risk SKUs", high_risk)

    st.markdown("---")

    # 🔴 High-risk SKUs chart
    st.markdown("### 🔴 Top 15 High-Risk SKUs")

    top_risk = data.sort_values("priority_score", ascending=False).head(15)

    fig_risk = px.bar(
        top_risk,
        x="sku_id",
        y="priority_score",
        color="priority_score",
        color_continuous_scale="Reds",
        labels={"sku_id": "SKU", "priority_score": "Risk Score"}
    )

    st.plotly_chart(fig_risk, use_container_width=True)

    # 📋 Detailed table
    st.markdown("### 📋 SKU Risk Details")
    st.dataframe(
        data.sort_values("priority_score", ascending=False),
        use_container_width=True
    )

# =================================================
# PAGE 2: TEMPERATURE COMPLIANCE (KEEP WORKING)
# =================================================
elif page == "Temperature Compliance":

    st.subheader("🌡 Temperature Compliance Analysis")

    status_counts = data["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]

    fig_pie = px.pie(
        status_counts,
        names="Status",
        values="Count",
        color="Status",
        color_discrete_map={
            "Compliant": "green",
            "Violation": "red"
        },
        title="Temperature Compliance Status"
    )

    st.plotly_chart(fig_pie, use_container_width=True)

    st.markdown("### ❌ Temperature Violations")
    st.dataframe(
        data[data["status"] == "Violation"],
        use_container_width=True
    )

    # Download report
    csv = data.to_csv(index=False).encode("utf-8")
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
st.caption("VelocityMart Warehouse Analytics Dashboard | Streamlit 🚀")
