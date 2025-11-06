import streamlit as st
import pandas as pd
import altair as alt
import bcrypt
from db import engine


def check_credentials():
    if (
        not st.session_state.username
        or not st.session_state.password
        or st.session_state.username != st.secrets["app"]["user"]
        or not bcrypt.checkpw(
            st.session_state.password.encode(), st.secrets["app"]["password"].encode()
        )
    ):
        st.warning("Tente novamente")
    else:
        st.session_state.logged_in = True


def login():
    with st.form("login"):
        st.text_input("Username", key="username")
        st.text_input("Password", key="password", type="password")
        st.form_submit_button("Login", on_click=check_credentials)


@st.cache_data
def get_stored_data():
    return pd.read_sql("SELECT * FROM budget", engine, parse_dates=["date"])


def main():
    if "logged_in" not in st.session_state:
        login()
        st.stop()

    st.sidebar.title("Navigation")
    choice = st.sidebar.radio(
        "options", ["Dashboard", "Upload Files"], label_visibility="hidden"
    )

    if choice == "Dashboard":
        show_dashboard()
    elif choice == "Upload Files":
        upload_files()


def create_bar_chart(data, title):
    chart = (
        alt.Chart(data)
        .mark_bar()
        .encode(
            x=alt.X(
                "category:O",
                sort=alt.EncodingSortField(
                    field="amount", op="sum", order="descending"
                ),
            ),
            y=alt.Y("sum(amount):Q"),
            tooltip=["category", "sum(amount)"],
        )
        .properties(title=title)
    )
    st.altair_chart(chart)


EXCLUDE = {"Taxes", "Investments", "Income"}


def _ensure_dt(df):
    if not pd.api.types.is_datetime64_any_dtype(df["date"]):
        df["date"] = pd.to_datetime(df["date"])
    return df


def _monthly_totals(df):
    m = df.copy()
    m["month"] = m["date"].dt.to_period("M").dt.to_timestamp()
    return m.groupby(["category", "month"], as_index=False)["amount"].sum()


def _avg_monthly_by_category(df):
    # average of monthly totals per category (excluding EXCLUDE)
    mt = _monthly_totals(df[~df["category"].isin(EXCLUDE)])
    return (
        mt.groupby("category", as_index=False)["amount"]
        .mean()
        .sort_values("amount", ascending=False)
    )


def _avg_monthly_by_year_and_category(df):
    # for each year+category, compute avg per month (exclude EXCLUDE)
    f = df[~df["category"].isin(EXCLUDE)].copy()
    f["month"] = f["date"].dt.to_period("M").dt.to_timestamp()
    mt = f.groupby(["category", "month"], as_index=False)["amount"].sum()
    mt["year"] = mt["month"].dt.year
    return mt.groupby(["category", "year"], as_index=False)["amount"].mean()


def _avg_per_month_for(df, category_name):
    sub = df[df["category"] == category_name]
    if sub.empty:
        return 0.0
    mt = _monthly_totals(sub)
    return float(mt["amount"].mean())


def show_dashboard():
    st.title("Dashboard")

    df = get_stored_data()
    df = df[df["category"] != "Ignore"].copy()
    df = _ensure_dt(df)

    # --- 1) Bar: avg monthly spend by category (exclude Taxes/Investments/Income)
    avg_monthly = _avg_monthly_by_category(df)
    bar = (
        alt.Chart(avg_monthly)
        .mark_bar()
        .encode(
            x=alt.X("category:N", sort="-y", title="Category"),
            y=alt.Y("amount:Q", title="Avg monthly spend"),
            tooltip=[alt.Tooltip("category:N"), alt.Tooltip("amount:Q", format=",.2f")],
        )
        .properties(
            title="Average Monthly Spend by Category (Excl. Taxes, Investments, Income)"
        )
    )
    st.altair_chart(bar)

    # --- 2) Line: avg expenses per year, lines per category (exclude Taxes/Investments/Income)
    yearly = _avg_monthly_by_year_and_category(df)
    sel = alt.selection_point(fields=["category"], bind="legend")
    line = (
        alt.Chart(yearly)
        .mark_line(point=True)
        .encode(
            x=alt.X("year:O", title="Year"),
            y=alt.Y("amount:Q", title="Avg monthly spend in year"),
            color=alt.Color("category:N", legend=alt.Legend(title="Category")),
            opacity=alt.condition(sel, alt.value(1.0), alt.value(0.15)),
            tooltip=[
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("amount:Q", title="Avg/month", format=",.2f"),
            ],
        )
        .add_params(sel)
        .properties(title="Avg Expenses per Year (Excl. Taxes, Investments, Income)")
    )
    st.altair_chart(line)

    # --- 3) Three columns: avg per month for Income, Taxes, Investments
    c1, c2, c3 = st.columns(3)
    avg_income = _avg_per_month_for(df, "Income")
    avg_taxes = _avg_per_month_for(df, "Taxes")
    avg_invest = _avg_per_month_for(df, "Investments")

    c1.metric("Income — Avg/month", f"€{avg_income:,.2f}")
    c2.metric("Taxes — Avg/month", f"€{avg_taxes:,.2f}")
    c3.metric("Investments — Avg/month", f"€{avg_invest:,.2f}")

    # --- 4) Investments as % of Income (using totals)
    total_investments = float(df.loc[df["category"] == "Investments", "amount"].sum())
    total_income = float(df.loc[df["category"] == "Income", "amount"].sum())
    pct = (total_investments / total_income * 100.0) if total_income else 0.0
    st.metric("Investments as % of Income", f"{pct:.2f}%")


@st.cache_data
def find_unique_rows_in_df(new_df, old_df):
    merged_df = new_df.merge(old_df, indicator=True, how="left")
    new_df = merged_df[merged_df["_merge"] == "left_only"].drop("_merge", axis=1)
    return new_df.reset_index(drop=True)


def replace_empty_with_none(x):
    if isinstance(x, str) and x.strip() == "":
        return None
    else:
        return x


# @st.cache_data
def process_tsv(file, file_type):
    max_cols = 0
    for line in file:
        num_cols = len(line.decode("ISO-8859-1").split("\t"))
        max_cols = max(max_cols, num_cols)

    file.seek(0)

    column_names = [f"Column_{i}" for i in range(max_cols)]

    if file_type == "Company Debit":
        df = pd.read_excel(file)
    else:
        df = pd.read_csv(
            file,
            sep="\t",
            names=column_names,
            header=None,
            encoding="ISO-8859-1",
        )

    if file_type == "Personal Debit" or file_type == "Personal Credit":
        columns_to_keep = [df.columns[i] for i in [1, 2, 3]]
    elif file_type == "Company Debit":
        columns_to_keep = [df.columns[i] for i in [0, 2, 3]]
    elif file_type == "Company Credit":
        columns_to_keep = [df.columns[i] for i in [1, 2, 3]]

    df = df[columns_to_keep]
    df = df.map(replace_empty_with_none)
    df = df.dropna(axis=0)
    df = df[1:]
    df.columns = ["date", "description", "amount"]
    try:
        if file_type == "Personal Debit":
            df.date = pd.to_datetime(df.date, format="%d-%m-%Y")
        elif file_type == "Personal Credit":
            df.date = pd.to_datetime(df.date, format="%d-%m-%Y ")
        elif file_type == "Company Debit":
            df.date = pd.to_datetime(df.date, format="%d/%m/%Y")
        elif file_type == "Company Credit":
            df.date = pd.to_datetime(df.date, format="%Y-%m-%d")
    except Exception:
        st.warning("Ficheiro Inválido")
        st.stop()
    if file_type in ["Personal Debit", "Personal Credit", "Company Credit"]:
        df["amount"] = df["amount"].str.replace(".", "", regex=False)
        df["amount"] = df["amount"].str.replace(",", ".", regex=False)
        df["amount"] = df["amount"].astype(float)
    df["amount"] = df["amount"].abs()
    return df.reset_index(drop=True)


def insert_row_into_database(row, origin, category):
    row["origin"] = origin
    row["category"] = category
    row_df = pd.DataFrame([row])
    row_df.to_sql("budget", engine, if_exists="append", index=False)
    st.session_state.current_row_index += 1


def upload_files():
    st.title("Upload Files")
    uploaded_file = st.file_uploader("Choose a file", type=["tsv", "xls", "xlsx"])

    if uploaded_file is not None:
        file_type = st.selectbox(
            "Select file type",
            ["Personal Debit", "Personal Credit", "Company Debit", "Company Credit"],
        )

        df = process_tsv(uploaded_file, file_type)
        stored_df = get_stored_data()
        new_data = find_unique_rows_in_df(
            df, stored_df[["date", "description", "amount"]]
        )
        if "current_row_index" not in st.session_state:
            st.session_state.current_row_index = 0

        origin_options = [
            "Personal",
            "Company",
        ]
        category_options = [
            "Appliances",
            "Car",
            "Charity",
            "Comissions",
            "Dining",
            "Dog",
            "Fun",
            "Health",
            "Ignore",
            "Income",
            "Insurance",
            "Investments",
            "Job",
            "Other",
            "Rent",
            "Salary",
            "Sports",
            "Taxes",
            "Transportation",
            "Travel",
            "Utilities",
        ]

        if st.session_state.current_row_index < len(new_data):
            row = new_data.iloc[st.session_state.current_row_index]
            st.write(row.astype(str))
            default_origin = "Personal" if "Personal" in file_type else "Company"

            default_category = "Other"
            matching_rows = stored_df[stored_df["description"] == row["description"]]
            if not matching_rows.empty:
                default_category = matching_rows.iloc[0]["category"]

            origin = st.selectbox(
                "Select origin",
                origin_options,
                index=origin_options.index(default_origin),
            )
            category = st.selectbox(
                "Select category",
                category_options,
                index=category_options.index(default_category),
            )
            st.button(
                "Confirm",
                on_click=insert_row_into_database,
                args=[row, origin, category],
            )
        else:
            st.write("All rows have been processed.")
            st.cache_data.clear()
    else:
        if "current_row_index" in st.session_state.keys():
            del st.session_state.current_row_index


if __name__ == "__main__":
    main()
