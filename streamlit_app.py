import os

import pandas as pd
import psycopg
import streamlit as st

st.set_page_config(page_title="Victorian Home Investment Screen", layout="wide")
st.title("Victorian Home Investment Screen")
st.caption("Indicative open-data screening only — not financial or property advice.")


@st.cache_data(ttl=3600)
def load_data(database_url: str) -> pd.DataFrame:
    with psycopg.connect(database_url) as connection:
        return pd.read_sql("select * from mart.vw_dashboard_roi", connection)


database_url = st.secrets.get("SUPABASE_DB_URL", os.getenv("SUPABASE_DB_URL"))
if not database_url:
    st.error("SUPABASE_DB_URL is not configured.")
    st.stop()

data = load_data(database_url)
if data.empty:
    st.warning("No certified ROI observations are available yet.")
    st.stop()

property_types = st.sidebar.multiselect(
    "Property type", sorted(data["property_type"].unique()), default=sorted(data["property_type"].unique())
)
bedrooms = st.sidebar.multiselect(
    "Bedrooms", sorted(data["bedrooms"].unique()), default=sorted(data["bedrooms"].unique())
)
filtered = data[data["property_type"].isin(property_types) & data["bedrooms"].isin(bedrooms)]

left, middle, right = st.columns(3)
left.metric("Matched suburbs", filtered["canonical_suburb_key"].nunique())
middle.metric("Median gross yield", f"{filtered['estimated_gross_yield_pct'].median():.2f}%")
right.metric("Median price", f"A${filtered['median_price'].median():,.0f}")

st.subheader("Yield and historical growth")
chart = filtered.dropna(subset=["price_growth_cagr_pct"]).set_index("canonical_suburb_key")
st.scatter_chart(
    chart,
    x="price_growth_cagr_pct",
    y="estimated_gross_yield_pct",
    size="median_price",
    color="property_type",
)

st.subheader("Screening table")
st.dataframe(
    filtered.sort_values(["indicative_score", "estimated_gross_yield_pct"], ascending=False),
    use_container_width=True,
    hide_index=True,
)
st.info(
    "Gross yield excludes vacancy, finance, rates, tax, insurance, maintenance, strata and transaction costs."
)
