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
    sku_master = pd.read_csv(BASE_DIR / "sku_master_converted.xlsx.csv")
    orders = pd.read_csv(BASE_DIR / "order_transactions_converted.xlsx.csv")
    warehouse = pd.read_csv(BASE_DIR / "warehouse_constraints_converted.xlsx.csv")

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

    weekly_picks = orders.groupby("sku_id").size()
    temp_df["weekly_picks"] = temp_df["sku_id"].map(weekly_picks).fillna(0)

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

if data.empty:
    st.warning("No data available to display.")
    st.stop()

# -------------------------------------------------
# PAGE 1: Warehouse Health Overview
# -------------------------------------------------
if page == "Warehouse Health Overview":

    st.subheader("📊 Warehouse Health Overview")

    total_skus = len(data)
    mismatched = (data["required_temp"] != data["current_zone"]).sum()

    col1, col2, col3 = st.columns(3)
    col1.metric("Total SKUs", total_skus)
    col2.metric("Temperature Violations", mismatched)
    col3.metric(
        "High Risk SKUs",
        (data["priority_score"] > data["priority_score"].median()).sum()
    )

    st.markdown("---")

    st.subheader("🔍 Key Insights")
    st.write(
        f"""
        • **{round((mismatched/total_skus)*100,1)}%** of SKUs are in incorrect temperature zones  
        • High-risk SKUs contribute disproportionately to spoilage risk  
        • Prioritized relocation can reduce losses
        """
    )

    st.markdown("---")

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
        lambda x: "Compliant" if x["required_temp"] == x["current_zone"] else "Violation",
        axis=1
    )

    status_counts = compliance_df["status"].value_counts().reset_index()
    status_counts.columns = ["Status", "Count"]

    fig = px.bar(
        status_counts,
        x="Status",
        y="Count",
        color="Status",
        title="Temperature Compliance Status",
        color_discrete_map={
            "Compliant": "green",
            "Violation": "red"
        }
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ❌ Violating SKUs")
    st.dataframe(
        compliance_df[compliance_df["status"] == "Violation"]
        .sort_values("priority_score", ascending=False),
        use_container_width=True
    )

    st.download_button(
        "⬇ Download Compliance Report",
        compliance_df.to_csv(index=False),
        "temperature_compliance_report.csv",
        "text/csv"
    )

# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown("---")
st.caption("VelocityMart Analytics Dashboard | Phase-1 MVP | Built with Streamlit 🚀")

