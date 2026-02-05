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
# Sidebar
# -------------------------------------------------
st.sidebar.title("Navigation")
page = st.sidebar.radio(
    "Go to",
    ["Warehouse Health Overview", "Temperature Compliance"]
)

data = load_data()


# =================================================
# PAGE 1: Warehouse Health Overview (RESTORED)
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

    top_risk = data.sort_values("priority_score", ascending=False).head(15)

    fig = px.bar(
        top_risk,
        x="sku_id",
        y="priority_score",
        color="priority_score",
        color_continuous_scale="Reds"
    )

    fig.update_layout(
        xaxis_title="SKU ID",
        yaxis_title="Risk Score",
        plot_bgcolor="#111111",
        paper_bgcolor="#111111"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### 📋 Detailed Risk Table")
    st.dataframe(
        data.sort_values("priority_score", ascending=False),
        use_container_width=True
    )


# =================================================
# PAGE 2: Temperature Compliance (100% FIXED)
# =================================================
elif page == "Temperature Compliance":

    st.subheader("🌡 Temperature Compliance Analysis")

    df = data.copy()
    df["Status"] = df.apply(
        lambda x: "Compliant" if x["required_temp"] == x["current_zone"] else "Violation",
        axis=1
    )

    # -------- FORCE COUNTS --------
    status_counts = pd.DataFrame({
        "Status": ["Compliant", "Violation"],
        "Count": [
            (df["Status"] == "Compliant").sum(),
            (df["Status"] == "Violation").sum()
        ]
    })

    # -------- GUARANTEED VISIBLE BAR CHART --------
    fig = px.bar(
        status_counts,
        x="Status",
        y="Count",
        color="Status",
        text="Count",
        color_discrete_map={
            "Compliant": "#2ecc71",
            "Violation": "#e74c3c"
        }
    )

    fig.update_traces(
        textposition="outside",
        width=0.6
    )

    fig.update_layout(
        title="Temperature Compliance Status",
        xaxis_title="Status",
        yaxis_title="Number of SKUs",
        yaxis=dict(
            range=[0, status_counts["Count"].max() * 1.3 + 1]
        ),
        plot_bgcolor="#111111",
        paper_bgcolor="#111111",
        font=dict(size=14)
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ❌ SKUs with Temperature Violations")

    st.dataframe(
        df[df["Status"] == "Violation"],
        use_container_width=True
    )

    csv = df.to_csv(index=False).encode("utf-8")
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
