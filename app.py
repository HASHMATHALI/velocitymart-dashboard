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

    # Normalize text columns (CRITICAL FIX)
    sku_master["temp_req"] = sku_master["temp_req"].astype(str).str.strip().str.lower()
    warehouse["temp_zone"] = warehouse["temp_zone"].astype(str).str.strip().str.lower()

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

    # Handle missing zones
    df["current_zone"] = df["current_zone"].fillna("unknown")

    # Weekly pick count
    weekly_picks = orders.groupby("sku_id").size()
    df["weekly_picks"] = df["sku_id"].map(weekly_picks).fillna(0)

    # Risk score
    df["priority_score"] = df["weekly_picks"] * 3

    return df


data = load_data()

# -------------------------------------------------
# Sidebar
# -------------------------------------------------
page = st.sidebar.radio(
    "Navigation",
    ["Warehouse Health Overview", "Temperature Compliance"]
)

# -------------------------------------------------
# PAGE 1
# -------------------------------------------------
if page == "Warehouse Health Overview":

    st.subheader("📊 Warehouse Health Overview")

    c1, c2, c3 = st.columns(3)

    with c1:
        st.metric("Total SKUs", len(data))

    with c2:
        st.metric(
            "Temperature Violations",
            (data["required_temp"] != data["current_zone"]).sum()
        )

    with c3:
        st.metric(
            "High Risk SKUs",
            (data["priority_score"] > data["priority_score"].median()).sum()
        )

    fig = px.bar(
        data.sort_values("priority_score", ascending=False).head(15),
        x="sku_id",
        y="priority_score",
        title="Top 15 High-Risk SKUs",
        color="priority_score",
        color_continuous_scale="Reds"
    )

    st.plotly_chart(fig, use_container_width=True)
    st.dataframe(data.sort_values("priority_score", ascending=False))


# -------------------------------------------------
# PAGE 2 (FULLY FIXED)
# -------------------------------------------------
else:

    st.subheader("🌡 Temperature Compliance Analysis")

    compliance_df = data.copy()
    compliance_df["status"] = compliance_df.apply(
        lambda x: "Compliant"
        if x["required_temp"] == x["current_zone"]
        else "Violation",
        axis=1
    )

    # COUNT STATUS (FORCE BOTH VALUES)
    status_counts = pd.DataFrame({
        "Status": ["Compliant", "Violation"],
        "Count": [
            (compliance_df["status"] == "Compliant").sum(),
            (compliance_df["status"] == "Violation").sum()
        ]
    })

    # DEBUG (YOU CAN REMOVE LATER)
    st.caption("🔍 Debug Counts")
    st.write(status_counts)

    fig = px.bar(
        status_counts,
        x="Status",
        y="Count",
        text="Count",
        title="Temperature Compliance Status",
        color="Status",
        color_discrete_map={
            "Compliant": "#2ecc71",
            "Violation": "#e74c3c"
        }
    )

    fig.update_traces(textposition="outside")
    fig.update_layout(
        yaxis_title="Number of SKUs",
        yaxis=dict(range=[0, max(1, status_counts["Count"].max() + 5)]),
        plot_bgcolor="rgba(0,0,0,0)"
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ❌ Violating SKUs")
    st.dataframe(compliance_df[compliance_df["status"] == "Violation"])

    st.download_button(
        "⬇ Download Compliance Report",
        compliance_df.to_csv(index=False),
        "temperature_compliance_report.csv"
    )


st.markdown("---")
st.caption("VelocityMart Analytics Dashboard | Streamlit 🚀")


