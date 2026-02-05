import streamlit as st
import pandas as pd
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

    weekly_picks = orders.groupby("sku_id").size()
    df["weekly_picks"] = df["sku_id"].map(weekly_picks).fillna(0)

    df["priority_score"] = df["weekly_picks"] * 3

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
# PAGE 1: Warehouse Health Overview (STABLE)
# =================================================
if page == "Warehouse Health Overview":

    st.subheader("🏭 Warehouse Health Overview")

    col1, col2, col3 = st.columns(3)

    col1.metric("Total SKUs", len(data))
    col2.metric(
        "Temperature Mismatches",
        (data["required_temp"] != data["current_zone"]).sum()
    )
    col3.metric(
        "High Risk SKUs",
        (data["priority_score"] > data["priority_score"].median()).sum()
    )

    st.markdown("---")
    st.markdown("### 🔥 Top 15 High-Risk SKUs")

    top_risk = (
        data.sort_values("priority_score", ascending=False)
        .head(15)
        .set_index("sku_id")[["priority_score"]]
    )

    st.bar_chart(top_risk, height=400)

    st.markdown("### 📋 Detailed Risk Table")
    st.dataframe(
        data.sort_values("priority_score", ascending=False),
        use_container_width=True
    )


# =================================================
# PAGE 2: Temperature Compliance (BULLETPROOF)
# =================================================
elif page == "Temperature Compliance":

    st.subheader("🌡 Temperature Compliance Analysis")

    df = data.copy()
    df["Status"] = df.apply(
        lambda x: "Compliant" if x["required_temp"] == x["current_zone"] else "Violation",
        axis=1
    )

    # ---- Explicit aggregation ----
    status_counts = (
        df["Status"]
        .value_counts()
        .reindex(["Compliant", "Violation"], fill_value=0)
        .to_frame("Number of SKUs")
    )

    st.markdown("### Temperature Compliance Status")

    # ---- STREAMLIT NATIVE BAR CHART (CAN'T FAIL) ----
    st.bar_chart(status_counts, height=400)

    st.markdown("### ❌ SKUs with Temperature Violations")
    st.dataframe(
        df[df["Status"] == "Violation"],
        use_container_width=True
    )

    st.download_button(
        "⬇ Download Compliance Report",
        df.to_csv(index=False),
        "temperature_compliance_report.csv",
        "text/csv"
    )


# -------------------------------------------------
# Footer
# -------------------------------------------------
st.markdown("---")
st.caption("VelocityMart Warehouse Dashboard | Built with Streamlit 🚀")

