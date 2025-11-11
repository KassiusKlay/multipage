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


def show_dashboard():
    st.title("Dashboard")
    df = get_stored_data()

    # --- CORE: NUMBER OF MONTHS ---
    df["month"] = df["date"].dt.to_period("M")
    n_months = df["month"].nunique()
    st.caption(f"**Data coverage:** {n_months} distinct months")

    # --- EXCLUDE CATEGORIES ---
    EXCLUDE = {"Taxes", "Investments", "Income", "Ignore", "Salary", "Job"}

    # ==============================================================
    # 1. BAR CHART: Avg monthly spend per category (total / n_months)
    # ==============================================================
    spend_df = df[~df["category"].isin(EXCLUDE)]
    totals_by_cat = spend_df.groupby("category")["amount"].sum()
    avg_by_cat = totals_by_cat / n_months
    avg_by_cat = avg_by_cat.sort_values(ascending=False).reset_index()
    avg_by_cat.columns = ["category", "amount"]

    bar = (
        alt.Chart(avg_by_cat)
        .mark_bar()
        .encode(
            x=alt.X("category:N", sort="-y", title="Category"),
            y=alt.Y("amount:Q", title="Avg monthly spend"),
            tooltip=[
                alt.Tooltip("category:N"),
                alt.Tooltip("amount:Q", format=",.0f", title="Avg/month"),
            ],
        )
        .properties(title="Average Monthly Spend by Category")
    )
    st.altair_chart(bar, use_container_width=True)

    # ==============================================================
    # 2. LINE CHART: Avg monthly spend PER YEAR (correctly)
    # ==============================================================
    # First: count how many months of data exist per year
    spend_df["year"] = spend_df["date"].dt.year
    spend_df["month"] = spend_df["date"].dt.to_period("M")

    # Total spent per category & year
    yearly_totals = spend_df.groupby(["category", "year"])["amount"].sum().reset_index()

    # Count distinct months per year (across all data — not just this category)
    months_in_year = spend_df.groupby("year")["month"].nunique().reset_index()
    months_in_year.columns = ["year", "months_in_year"]

    # Merge to get correct divisor
    yearly_avg = yearly_totals.merge(months_in_year, on="year")
    yearly_avg["avg_monthly"] = yearly_avg["amount"] / yearly_avg["months_in_year"]

    # Clean up for chart
    yearly_avg = yearly_avg[["category", "year", "avg_monthly"]]

    # Plot
    sel = alt.selection_point(fields=["category"], bind="legend")
    line = (
        alt.Chart(yearly_avg)
        .mark_line(point=True)
        .encode(
            x=alt.X("year:O", title="Year"),
            y=alt.Y("avg_monthly:Q", title="Avg monthly spend in year"),
            color=alt.Color("category:N", legend=alt.Legend(title="Category")),
            opacity=alt.condition(sel, alt.value(1), alt.value(0.2)),
            tooltip=[
                alt.Tooltip("year:O", title="Year"),
                alt.Tooltip("category:N", title="Category"),
                alt.Tooltip("avg_monthly:Q", title="Avg/month", format=",.0f"),
            ],
        )
        .add_params(sel)
        .properties(title="Average Monthly Spend per Year (per actual months in year)")
    )
    st.altair_chart(line, use_container_width=True)

    # ==============================================================
    # 3. METRICS: Income, Taxes, Investments
    # ==============================================================
    def avg_for(cat):
        total = df[df["category"] == cat]["amount"].sum()
        return total / n_months if n_months > 0 else 0.0

    avg_income = avg_for("Income")
    avg_taxes = avg_for("Taxes")
    avg_invest = avg_for("Investments")

    # NEW: Total spend (excluding EXCLUDE)
    total_spend = spend_df["amount"].sum()
    avg_spend = total_spend / n_months if n_months > 0 else 0.0

    # 4-column layout
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Income — Avg/month", f"€{avg_income:,.0f}")
    c2.metric("Taxes — Avg/month", f"€{avg_taxes:,.0f}")
    c3.metric("Investments — Avg/month", f"€{avg_invest:,.0f}")
    c4.metric("**Total Spend — Avg/month**", f"€{avg_spend:,.0f}")

    # ==============================================================
    # 4. Investments % of Income
    # ==============================================================
    total_income = df[df["category"] == "Income"]["amount"].sum()
    total_invest = df[df["category"] == "Investments"]["amount"].sum()
    pct = (total_invest / total_income * 100) if total_income > 0 else 0
    st.metric("Investments as % of Income", f"{pct:.1f}%")

    # ==============================================================
    # 5. Summary Footer
    # ==============================================================
    st.caption(
        f"All averages = **total amount ÷ {n_months} months** | "
        f"Data from {df['date'].min().strftime('%b %Y')} to {df['date'].max().strftime('%b %Y')}"
    )


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
