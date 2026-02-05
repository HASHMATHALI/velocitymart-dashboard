import streamlit as st
import pandas as pd
import plotly.graph_objects as go
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
    sku = pd.read_csv(BASE_DIR / "sku_master_converted.xlsx.csv")
    orders = pd.read_csv(BASE_DIR / "order_transactions_converted.xlsx.csv")
    wh = pd.read_csv(BASE_DIR / "warehouse_constraints_converted.xlsx.csv")

    # Normalize temperature columns
    sku["temp_req"] = sku["temp_req"].astype(str).str.strip().str.lower()
    wh["temp_zone"] = wh["temp_zone"].astype(str).str.strip().str.lower()

    df = sku.merge(
        wh[["slot_id", "temp_zone"]],
        left_on="current_slot",
        right_on="slot_id",
        how="left"
    )

    df.rename(columns={
        "temp_req": "required_temp",
        "temp_zone": "current_zone"
    }, inplace=True)

    df["current_zone"] = df["current_zone"].fillna("unknown")

    weekly = orders.groupby("sku_id").size()
    df["weekly_picks"] = df["sku_id"].map(weekly).fillna(0).astype(int)

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

    c1.metric("Total SKUs", int(len(data)))
    c2.metric(
        "Temperature Violations",
        int((data["required_temp"] != data["current_zone"]).sum())
    )
    c3.metric(
        "High Risk SKUs",
        int((data["priority_score"] > data["priority_score"].median()).sum())
    )

    st.dataframe(
        data.sort_values("priority_score", ascending=False),
        use_container_width=True
    )


# -------------------------------------------------
# PAGE 2 — GUARANTEED GRAPH
# -------------------------------------------------
else:

    st.subheader("🌡 Temperature Compliance Analysis")

    data["status"] = [
        "Compliant" if r == c else "Violation"
        for r, c in zip(data["required_temp"], data["current_zone"])
    ]

    compliant_count = int((data["status"] == "Compliant").sum())
    violation_count = int((data["status"] == "Violation").sum())

    # 🚨 HARD GUARANTEE DATA
    status_labels = ["Compliant", "Violation"]
    status_values = [compliant_count, violation_count]

    # DEBUG — YOU WILL SEE NUMBERS
    st.info(f"Compliant: {compliant_count} | Violations: {violation_count}")

    fig = go.Figure()

    fig.add_bar(
        x=status_labels,
        y=status_values,
        marker_color=["#2ecc71", "#e74c3c"],
        text=status_values,
        textposition="outside"
    )

    fig.update_layout(
        title="Temperature Compliance Status",
        xaxis_title="Status",
        yaxis_title="Number of SKUs",
        yaxis=dict(
            range=[0, max(5, max(status_values) + 5)]
        ),
        bargap=0.4,
        plot_bgcolor="rgba(0,0,0,0)",
        paper_bgcolor="rgba(0,0,0,0)",
        font=dict(size=14)
    )

    st.plotly_chart(fig, use_container_width=True)

    st.markdown("### ❌ Violating SKUs")
    st.dataframe(
        data[data["status"] == "Violation"],
        use_container_width=True
    )

    st.download_button(
        "⬇ Download Compliance Report",
        data.to_csv(index=False),
        "temperature_compliance_report.csv"
    )


st.markdown("---")
st.caption("VelocityMart Analytics Dashboard | Production-ready Streamlit App 🚀")




