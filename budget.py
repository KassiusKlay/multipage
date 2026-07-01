import streamlit as st
import pandas as pd
import altair as alt
from db import engine


@st.cache_data
def get_stored_data():
    return pd.read_sql("SELECT * FROM budget", engine, parse_dates=["date"])


def main():
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
    spend_df = df[~df["category"].isin(EXCLUDE)].copy()
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
    st.altair_chart(bar, width="stretch")

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
    st.altair_chart(line, width="stretch")

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


FILE_TYPES = [
    "Personal Debit",
    "Personal Credit",
    "Company Debit",
    "Company Credit",
]

CATEGORY_OPTIONS = [
    "Appliances",
    "Car",
    "Charity",
    "Comissions",
    "Dining",
    "Dog",
    "Fun",
    "Health",
    "House",
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


def origin_for_file_type(file_type):
    return "Personal" if "Personal" in file_type else "Company"


def build_category_lookup(stored_df):
    if stored_df.empty:
        return {}, {}

    grouped = stored_df.groupby("description")["category"]
    default_category = grouped.apply(
        lambda values: values.mode().iloc[0] if not values.empty else "Other"
    )
    past_categories = grouped.apply(
        lambda values: ", ".join(sorted(values.unique())) if values.nunique() > 1 else ""
    )
    return default_category.to_dict(), past_categories.to_dict()


def prepare_new_rows(parsed_dfs, stored_df):
    if not parsed_dfs:
        return pd.DataFrame()

    combined = pd.concat(parsed_dfs, ignore_index=True)
    combined = combined.drop_duplicates(subset=["date", "description", "amount"])
    new_data = find_unique_rows_in_df(
        combined, stored_df[["date", "description", "amount"]]
    )
    if new_data.empty:
        return new_data

    default_category, past_categories = build_category_lookup(stored_df)
    new_data = new_data.copy()
    is_known = new_data["description"].isin(default_category)
    new_data["category"] = new_data["description"].map(default_category)
    new_data.loc[~is_known, "category"] = None
    new_data["past_categories"] = new_data["description"].map(past_categories).fillna("")
    new_data["status"] = "New"
    new_data.loc[is_known, "status"] = "Known"
    new_data.loc[new_data["past_categories"] != "", "status"] = "Review"

    status_order = {"New": 0, "Review": 1, "Known": 2}
    return (
        new_data.assign(_sort=new_data["status"].map(status_order))
        .sort_values(["_sort", "date", "description"])
        .drop(columns="_sort")
        .reset_index(drop=True)
    )


def missing_categories(rows_df):
    category = rows_df["category"]
    return category.isna() | category.astype(str).str.strip().eq("")


def insert_rows_batch(rows_df):
    if missing_categories(rows_df).any():
        raise ValueError("All rows must have a category before upload.")

    rows_df[["date", "description", "amount", "origin", "category"]].to_sql(
        "budget", engine, if_exists="append", index=False
    )
    get_stored_data.clear()
    st.session_state.pending_budget_rows = None


def upload_files():
    st.title("Upload Files")
    if "pending_budget_rows" not in st.session_state:
        st.session_state.pending_budget_rows = None

    uploaded_files = st.file_uploader(
        "Choose files",
        type=["tsv", "xls", "xlsx"],
        accept_multiple_files=True,
    )

    if uploaded_files:
        st.subheader("File types")
        file_types = {}
        for i, uploaded_file in enumerate(uploaded_files):
            file_types[uploaded_file.name] = st.selectbox(
                uploaded_file.name,
                FILE_TYPES,
                key=f"budget_file_type_{i}",
            )

        if st.button("Process files"):
            parsed_dfs = []
            for uploaded_file in uploaded_files:
                file_type = file_types[uploaded_file.name]
                df = process_tsv(uploaded_file, file_type)
                df["origin"] = origin_for_file_type(file_type)
                parsed_dfs.append(df)

            stored_df = get_stored_data()
            st.session_state.pending_budget_rows = prepare_new_rows(
                parsed_dfs, stored_df
            )

    pending = st.session_state.get("pending_budget_rows")
    if pending is not None and not pending.empty:
        n_new = (pending["status"] == "New").sum()
        st.subheader(f"New rows ({len(pending)})")
        if n_new:
            st.caption(f"{n_new} new description(s) at the top — category must be set before upload.")

        display_cols = [
            "status",
            "date",
            "description",
            "amount",
            "origin",
            "category",
            "past_categories",
        ]
        column_config = {
            "status": st.column_config.TextColumn("Status", disabled=True),
            "date": st.column_config.DatetimeColumn("Date", disabled=True),
            "description": st.column_config.TextColumn("Description", disabled=True),
            "amount": st.column_config.NumberColumn("Amount", format="%.2f", disabled=True),
            "origin": st.column_config.TextColumn("Origin", disabled=True),
            "category": st.column_config.SelectboxColumn(
                "Category",
                options=CATEGORY_OPTIONS,
                required=False,
            ),
            "past_categories": st.column_config.TextColumn(
                "Past categories",
                disabled=True,
                help="Shown when this description had multiple categories before.",
            ),
        }

        edited = st.data_editor(
            pending[display_cols],
            column_config=column_config,
            hide_index=True,
            width="stretch",
            key="budget_pending_editor",
        )

        n_missing = missing_categories(edited).sum()
        if n_missing:
            st.warning(f"{n_missing} row(s) still need a category.")

        if st.button("Confirm all", type="primary", disabled=n_missing > 0):
            insert_rows_batch(edited)
            st.success(f"{len(edited)} rows inserted.")
            st.rerun()

        if st.button("Discard"):
            st.session_state.pending_budget_rows = None
            st.rerun()

    elif pending is not None and pending.empty:
        st.info("No new rows — all transactions are already in the database.")
        if st.button("Clear"):
            st.session_state.pending_budget_rows = None
            st.rerun()
    elif uploaded_files and st.session_state.get("pending_budget_rows") is None:
        st.caption("Select file types and click **Process files**.")
    else:
        st.session_state.pop("pending_budget_rows", None)


if __name__ == "__main__":
    main()
