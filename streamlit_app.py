import os

import pandas as pd
import psycopg
import streamlit as st
from psycopg import Error as PostgresError
from streamlit.errors import StreamlitSecretNotFoundError

st.set_page_config(
    page_title="Victorian Home Investment Screen",
    page_icon="🏠",
    layout="wide",
)
st.title("Victorian Home Investment Screen")
st.caption(
    "Compare suburb cohorts using Victorian Government median prices and rents. "
    "Indicative screening only — not financial or property advice."
)


@st.cache_data(ttl=3600)
def load_data(database_url: str | None, local_data_path: str | None) -> pd.DataFrame:
    if local_data_path:
        return pd.read_parquet(local_data_path).rename(
            columns={
                "observation_date": "price_observation_date",
                "period_end": "rent_period_end",
            }
        )
    with psycopg.connect(database_url) as connection:
        return pd.read_sql("select * from mart.vw_dashboard_roi", connection)


local_data_path = os.getenv("DASHBOARD_DATA_PATH")
database_url = os.getenv("SUPABASE_DB_URL")
if not database_url and not local_data_path:
    try:
        database_url = st.secrets.get("SUPABASE_DB_URL")
    except StreamlitSecretNotFoundError:
        database_url = None
if not database_url and not local_data_path:
    st.error("SUPABASE_DB_URL is not configured. Local development may use DASHBOARD_DATA_PATH.")
    st.stop()

try:
    data = load_data(database_url, local_data_path)
except (OSError, PostgresError):
    st.error("The certified data source is temporarily unavailable. Please try again later.")
    st.stop()
if data.empty:
    st.warning("No certified ROI observations are available yet.")
    st.stop()

st.sidebar.header("Screening filters")
property_types = st.sidebar.multiselect(
    "Property type",
    sorted(data["property_type"].unique()),
    default=sorted(data["property_type"].unique()),
)
bedrooms = st.sidebar.multiselect(
    "Bedrooms", sorted(data["bedrooms"].unique()), default=sorted(data["bedrooms"].unique())
)
price_floor = int(data["median_price"].min())
price_ceiling = int(data["median_price"].max())
maximum_price = (
    st.sidebar.slider(
        "Maximum median price",
        min_value=price_floor,
        max_value=price_ceiling,
        value=price_ceiling,
        step=10_000,
        format="A$%d",
    )
    if price_floor < price_ceiling
    else price_ceiling
)
yield_floor = float(data["estimated_gross_yield_pct"].min())
yield_ceiling = float(data["estimated_gross_yield_pct"].max())
minimum_yield = (
    st.sidebar.slider(
        "Minimum gross yield",
        min_value=yield_floor,
        max_value=yield_ceiling,
        value=yield_floor,
        step=0.1,
        format="%.1f%%",
    )
    if yield_floor < yield_ceiling
    else yield_floor
)
filtered = data[
    data["property_type"].isin(property_types)
    & data["bedrooms"].isin(bedrooms)
    & (data["median_price"] <= maximum_price)
    & (data["estimated_gross_yield_pct"] >= minimum_yield)
]

if filtered.empty:
    st.warning("No cohorts match the current filters. Widen the price or yield range.")
    st.stop()

left, middle, right, fourth = st.columns(4)
left.metric("Matched suburbs", filtered["canonical_suburb_key"].nunique())
middle.metric("Median gross yield", f"{filtered['estimated_gross_yield_pct'].median():.2f}%")
right.metric("Median price", f"A${filtered['median_price'].median():,.0f}")
median_score = filtered["indicative_score"].median()
fourth.metric("Median score", f"{median_score:.1f}" if pd.notna(median_score) else "—")

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
display_columns = {
    "canonical_suburb_key": "Suburb",
    "property_type": "Property type",
    "bedrooms": "Bedrooms",
    "median_price": "Median price",
    "median_weekly_rent": "Weekly rent",
    "estimated_gross_yield_pct": "Gross yield %",
    "price_growth_cagr_pct": "Price CAGR %",
    "indicative_score": "Score",
    "price_observation_date": "Price date",
    "rent_period_end": "Rent date",
}
screen = filtered[list(display_columns)].rename(columns=display_columns)
st.dataframe(
    screen.sort_values(["Score", "Gross yield %"], ascending=False),
    width="stretch",
    hide_index=True,
    column_config={
        "Median price": st.column_config.NumberColumn(format="A$%.0f"),
        "Weekly rent": st.column_config.NumberColumn(format="A$%.0f"),
        "Gross yield %": st.column_config.NumberColumn(format="%.2f%%"),
        "Price CAGR %": st.column_config.NumberColumn(format="%.2f%%"),
        "Score": st.column_config.NumberColumn(format="%.1f"),
    },
)
st.info(
    "Gross yield excludes vacancy, finance, rates, tax, insurance, maintenance, strata and transaction costs."
)
freshness = (
    f"Latest published database timestamp: "
    f"{pd.to_datetime(data['published_at']).max():%d %b %Y, %H:%M %Z}. "
    if "published_at" in data
    else "Local validated data preview. "
)
st.caption(freshness + "Prices are property-type medians; rental cohorts retain bedroom grain.")
