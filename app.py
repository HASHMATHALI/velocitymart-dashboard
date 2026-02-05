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

# Base directory (works locally + Streamlit Cloud)
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

    # Column validation
    required_sku_cols = {"sku_id", "current_slot", "temp_req"}
    required_wh_cols = {"slot_id", "temp_zone"}

    if not required_sku_cols.issubset(sku_master.columns):
        st.error("❌ sku_master file missing required columns")
        st.stop()

    if not required_wh_cols.issubset(warehouse.columns):
        st.error("❌ warehouse_constraints file missing required columns")
        st.stop()

    # Merge temperature zones
    temp_df = sku_master.merge(
        warehouse[["slot_id", "temp_zone"]],
        left_on="current_slot",
        right_on="slot_id",
        how="left"
    )

    temp_df.rename(
        columns={
            "temp_req": "required_temp",
            "temp_zone": "current_zone"
        },
        inplace=True
    )

    # Weekly pick count
    weekly_picks = orders.groupby("sku_id").size()
    temp_df["weekly_picks"] = temp_df["sku_id"].map(weekly_picks).fillna(0)

    # Risk calculation
    temp_df["days_at_risk"] = 3
    temp_df["priority_score"] = temp_df["weekly_picks"] * temp_df["days_at_risk"]

    return temp_df


# -------------------------------------------------
# Sidebar Navigation
# -------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Warehouse Health Overview", "Temperature Compliance"]
)

# -------------------------------------------------
# Load Dataset
# -------------------------------------------------
data = load_data()


# -------------------------------------------------
# PAGE 1: Warehouse Health Overview
# -------------------------------------------------
if page == "Warehouse Health Overview":

    st.subheader("📊 Warehouse Health Overview")

    col1, col2, col3 = st.columns(3)

    with col1:
        st.metric("Total SKUs", len(data))

    with col2:
        mismatched = (data["required_temp"] != data["current_zone"]).sum()
        st.metric("Temp Mismatches", mismatched)

    with col3:
        st.metric(
            "High Risk SKUs",
            (data["priority_score"] > data["priority_score"].median()).sum()
        )

    st.markdown("---")

    # Priority chart
    fig = px.bar(
        data.sort_values("priority_score", ascending=False).head(15),
        x="sku_id",
        y="priority_score",
        title="Top 15 High-Risk SKUs",
        color="priority_score",
        color_continuous_scale="Reds"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📋 SKU Risk Table")
    st.dataframe(
        data.sort_values("priority_score", ascending=False),
        use_container_width=True
    )


# -------------------------------------------------
# PAGE 2: Temperature Compliance
# -------------------------------------------------
elif page == "Temperature Compliance":

    st.subheader("🌡 Temperature Compliance Analysis")

    compliance_df = data.copy()
    compliance_df["status"] = compliance_df.apply(
        lambda x: "Compliant" if x["required_temp"] == x["current_zone"] else "Mismatch",
        axis=1
    )

    fig = px.pie(
        compliance_df,
        names="status",
        title="Temperature Compliance Status",
        color="status",
        color_discrete_map={
            "Compliant": "green",
            "Mismatch": "red"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ❌ Temperature Mismatches")
    st.dataframe(
        compliance_df[compliance_df["status"] == "Mismatch"],
        use_container_width=True
    )

    # Download
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
st.caption("VelocityMart Analytics Dashboard | Built with Streamlit 🚀")

