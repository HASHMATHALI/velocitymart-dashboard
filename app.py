import streamlit as st
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
from pathlib import Path
from datetime import datetime

# ---------------- CONFIG ----------------
st.set_page_config(
    page_title="VelocityMart Warehouse Dashboard",
    page_icon="📦",
    layout="wide"
)

BASE_DIR = Path(__file__).parent

# ---------------- DATA LOADING ----------------
@st.cache_data
def load_data():
    try:
        sku_master = pd.read_excel(BASE_DIR / "sku_master_converted.xlsx.csv")
        orders = pd.read_excel(BASE_DIR / "order_transactions_converted.xlsx.csv")
        warehouse = pd.read_excel(BASE_DIR / "warehouse_constraints_converted.xlsx")
    except Exception as e:
        st.error(f"❌ File load error: {e}")
        st.stop()

    # Required columns check
    if not {"sku_id", "current_slot", "temp_req"}.issubset(sku_master.columns):
        st.error("sku_master file missing required columns")
        st.stop()

    if not {"slot_id", "temp_zone"}.issubset(warehouse.columns):
        st.error("warehouse_constraints file missing required columns")
        st.stop()

    # Merge temperature info
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

    temp_df["weekly_picks"] = (
        orders.groupby("sku_id").size()
        .reindex(temp_df["sku_id"])
        .fillna(0)
        .values
    )

    temp_df["days_at_risk"] = 3
    temp_df["priority_score"] = temp_df["weekly_picks"] * temp_df["days_at_risk"]

    return temp_df

# ---------------- CHAOS SCORE ----------------
def chaos_score():
    return 15.8

# ---------------- SIDEBAR ----------------
page = st.sidebar.radio(
    "Navigation",
    ["Warehouse Health Overview", "Temperature Compliance"]
)

temperature = load_data()

# ================= PAGE 1 =================
if page == "Warehouse Health Overview":
    st.title("🏭 Warehouse Health Overview")

    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        fig = go.Figure(go.Indicator(
            mode="gauge+number",
            value=chaos_score(),
            title={"text": "Warehouse Chaos Score"},
            gauge={
                "axis": {"range": [0, 100]},
                "steps": [
                    {"range": [0, 10], "color": "green"},
                    {"range": [10, 20], "color": "yellow"},
                    {"range": [20, 30], "color": "orange"},
                    {"range": [30, 100], "color": "red"},
                ],
            }
        ))
        st.plotly_chart(fig, use_container_width=True)

    c1, c2, c3 = st.columns(3)
    c1.metric("Fulfillment Time", "6.2 min", "+2.4")
    c2.metric("Spoilage Risk", "$16,900", "338 SKUs")
    c3.metric("Collision Exposure", "31,072", "+10 windows")

# ================= PAGE 2 =================
elif page == "Temperature Compliance":
    st.title("🌡️ Temperature Compliance")

    matrix = temperature.pivot_table(
        index="required_temp",
        columns="current_zone",
        values="sku_id",
        aggfunc="count",
        fill_value=0
    )

    fig = px.imshow(
        matrix,
        text_auto=True,
        color_continuous_scale="RdYlGn_r",
        labels=dict(x="Current Zone", y="Required Temp", color="SKU Count")
    )
    st.plotly_chart(fig, use_container_width=True)

    st.subheader("Priority SKU List")
    st.dataframe(
        temperature.sort_values("priority_score", ascending=False),
        use_container_width=True
    )

    st.download_button(
        "⬇️ Export CSV",
        temperature.to_csv(index=False),
        "temperature_relocation_plan.csv"
    )

    st.caption(f"Last updated: {datetime.now().strftime('%d %b %Y %H:%M')}")
