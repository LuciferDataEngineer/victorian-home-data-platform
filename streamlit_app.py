import os

import httpx
import pandas as pd
import psycopg
import streamlit as st
from psycopg import Error as PostgresError
from streamlit.errors import StreamlitSecretNotFoundError

from home_data.dashboard_auth import (
    request_password_recovery,
    sign_in,
    sign_up,
    update_password,
    verify_recovery_token,
)
from home_data.watchlists import WatchlistClient

st.set_page_config(
    page_title="Victorian Home Investment Screen",
    page_icon="🏠",
    layout="wide",
)


def setting(name: str) -> str | None:
    value = os.getenv(name)
    if value:
        return value
    try:
        return st.secrets.get(name)
    except StreamlitSecretNotFoundError:
        return None


def render_password_reset(supabase_url: str, publishable_key: str, token_hash: str) -> None:
    st.title("Reset your password")
    if "recovery_access_token" not in st.session_state:
        try:
            result = verify_recovery_token(supabase_url, publishable_key, token_hash)
        except (httpx.HTTPError, ValueError):
            st.error("This recovery link is invalid or expired.")
            st.stop()
        if not result.authenticated or not result.access_token:
            st.error(result.message)
            st.stop()
        st.session_state.recovery_access_token = result.access_token
    with st.form("password_reset_form"):
        password = st.text_input("New password", type="password", autocomplete="new-password")
        confirmation = st.text_input(
            "Confirm new password", type="password", autocomplete="new-password"
        )
        submitted = st.form_submit_button("Update password", type="primary")
    if submitted:
        if password != confirmation:
            st.error("Passwords do not match.")
        else:
            message = update_password(
                supabase_url,
                publishable_key,
                st.session_state.recovery_access_token,
                password,
            )
            if message.startswith("Password updated"):
                st.session_state.pop("recovery_access_token", None)
                st.query_params.clear()
                st.success(message)
            else:
                st.error(message)


def render_auth(supabase_url: str, publishable_key: str) -> None:
    st.title("Victorian Home Investment Screen")
    st.caption("Sign in to access the private property investment screening dashboard.")
    sign_in_tab, sign_up_tab = st.tabs(["Sign in", "Create account"])

    with sign_in_tab:
        with st.form("sign_in_form"):
            email = st.text_input("Email", autocomplete="email")
            password = st.text_input("Password", type="password", autocomplete="current-password")
            submitted = st.form_submit_button("Sign in", type="primary", width="stretch")
        if submitted:
            try:
                result = sign_in(supabase_url, publishable_key, email, password)
            except (httpx.HTTPError, ValueError):
                st.error("Authentication is temporarily unavailable. Please try again.")
            else:
                if result.authenticated:
                    st.session_state.authenticated = True
                    st.session_state.user_email = result.email
                    st.session_state.access_token = result.access_token
                    st.rerun()
                st.error(result.message)
        with st.expander("Forgot password?"):
            recovery_email = st.text_input("Recovery email", autocomplete="email")
            if st.button("Send reset link"):
                try:
                    message = request_password_recovery(
                        supabase_url,
                        publishable_key,
                        recovery_email,
                        "https://victorian-home-data-platform-khqoosevqis9pzjyzkd2se.streamlit.app/",
                    )
                    st.info(message)
                except httpx.HTTPError:
                    st.error("Password recovery is temporarily unavailable.")

    with sign_up_tab:
        with st.form("sign_up_form"):
            email = st.text_input("Email", key="signup_email", autocomplete="email")
            password = st.text_input(
                "Password (minimum 8 characters)",
                type="password",
                key="signup_password",
                autocomplete="new-password",
            )
            submitted = st.form_submit_button("Create account", width="stretch")
        if submitted:
            try:
                result = sign_up(supabase_url, publishable_key, email, password)
            except (httpx.HTTPError, ValueError):
                st.error("Authentication is temporarily unavailable. Please try again.")
            else:
                if result.authenticated:
                    st.session_state.authenticated = True
                    st.session_state.user_email = result.email
                    st.session_state.access_token = result.access_token
                    st.rerun()
                st.success(result.message)


supabase_url = setting("SUPABASE_URL")
publishable_key = setting("SUPABASE_PUBLISHABLE_KEY")
if not supabase_url or not publishable_key:
    st.error("Dashboard authentication is not configured.")
    st.stop()
recovery_token_hash = st.query_params.get("token_hash")
if recovery_token_hash and st.query_params.get("type") == "recovery":
    render_password_reset(supabase_url, publishable_key, recovery_token_hash)
    st.stop()
if not st.session_state.get("authenticated"):
    render_auth(supabase_url, publishable_key)
    st.stop()

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
database_url = setting("SUPABASE_DB_URL")
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
st.sidebar.caption(f"Signed in as {st.session_state.get('user_email', 'user')}")
if st.sidebar.button("Sign out", width="stretch"):
    for key in ("authenticated", "user_email", "access_token"):
        st.session_state.pop(key, None)
    st.rerun()
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

st.subheader("My watchlist alerts")
watchlist_client = WatchlistClient(
    supabase_url, publishable_key, st.session_state.get("access_token", "")
)
with st.expander("Add or update a watchlist", expanded=False):
    available = data.sort_values(["canonical_suburb_key", "property_type", "bedrooms"])
    cohort_labels = available.apply(
        lambda row: f"{row['canonical_suburb_key']} · {row['property_type']} · {row['bedrooms']} bed",
        axis=1,
    )
    selected_label = st.selectbox("Suburb cohort", cohort_labels.tolist())
    selected = available.loc[cohort_labels[cohort_labels == selected_label].index[0]]
    threshold_left, threshold_middle, threshold_right = st.columns(3)
    alert_yield = threshold_left.number_input(
        "Minimum gross yield %", min_value=0.0, value=float(selected["estimated_gross_yield_pct"]), step=0.1
    )
    alert_score = threshold_middle.number_input(
        "Minimum score",
        min_value=0.0,
        value=float(selected["indicative_score"] if pd.notna(selected["indicative_score"]) else 0),
        step=1.0,
    )
    alert_price = threshold_right.number_input(
        "Maximum median price", min_value=0.0, value=float(selected["median_price"]), step=10_000.0
    )
    if st.button("Save alert", type="primary"):
        try:
            watchlist_client.save(
                {
                    "canonical_suburb_key": selected["canonical_suburb_key"],
                    "property_type": selected["property_type"],
                    "bedrooms": int(selected["bedrooms"]),
                    "min_gross_yield_pct": alert_yield,
                    "min_score": alert_score,
                    "max_median_price": alert_price,
                }
            )
            st.success("Watchlist saved.")
        except httpx.HTTPError:
            st.error("The watchlist could not be saved. Confirm migration 002 has been applied.")

try:
    saved_watchlists = watchlist_client.list()
except httpx.HTTPError:
    st.info("Watchlists will be available after the database migration is applied.")
else:
    if not saved_watchlists:
        st.caption("No saved alerts yet.")
    for saved in saved_watchlists:
        label, action = st.columns([5, 1])
        label.write(
            f"**{saved['canonical_suburb_key']}** · {saved['property_type']} · "
            f"{saved['bedrooms']} bed · yield ≥ {saved['min_gross_yield_pct']}% · "
            f"score ≥ {saved['min_score']} · price ≤ A${saved['max_median_price']:,.0f}"
        )
        if action.button("Remove", key=f"delete-{saved['id']}"):
            try:
                watchlist_client.delete(saved["id"])
                st.rerun()
            except httpx.HTTPError:
                st.error("The watchlist could not be removed.")
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
