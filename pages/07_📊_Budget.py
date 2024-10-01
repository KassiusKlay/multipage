import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import altair as alt
from dateutil.parser import ParserError
import bcrypt


@st.cache_resource
def init_engine():
    return create_engine(
        f"postgresql://"
        f'{st.secrets["postgres"]["user"]}:'
        f'{st.secrets["postgres"]["password"]}@'
        f'{st.secrets["postgres"]["host"]}:'
        f'{st.secrets["postgres"]["port"]}/'
        f'{st.secrets["postgres"]["dbname"]}',
    )


engine = init_engine()


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
    st.altair_chart(chart, use_container_width=True)


def show_dashboard():
    st.title("Dashboard")

    df = get_stored_data()
    df = df[df["category"] != "Ignore"]

    personal_df = df[df["origin"] == "Personal"]
    company_df = df[df["origin"] == "Company"]

    create_bar_chart(personal_df, "Personal Expenses by Category")
    create_bar_chart(company_df, "Company Expenses by Category")

    # Calculate and display monthly averages for categories
    df["month"] = df["date"].dt.to_period("M")

    # Filter out "Income" and "Investments" categories
    filtered_df = df[~df["category"].isin(["Income", "Investments"])]

    # Get the full range of months
    all_months = pd.period_range(
        start=df["month"].min(), end=df["month"].max(), freq="M"
    )

    # Create a DataFrame with all categories and all months
    full_index = pd.MultiIndex.from_product(
        [filtered_df["category"].unique(), all_months], names=["category", "month"]
    )

    # Reindex the filtered DataFrame to include all months for each category, filling missing values with 0
    monthly_totals = (
        filtered_df.groupby(["category", "month"])["amount"]
        .sum()
        .reindex(full_index, fill_value=0)
        .reset_index()
    )

    # Calculate the monthly average for each category across all months
    monthly_averages = monthly_totals.groupby("category")["amount"].mean().reset_index()

    # Plot the chart
    monthly_averages_chart = (
        alt.Chart(monthly_averages)
        .mark_bar()
        .encode(
            x=alt.X(
                "category:N",
                sort=alt.EncodingSortField(
                    field="amount", op="mean", order="descending"
                ),
            ),
            y="amount:Q",
            tooltip=["category", "amount"],
        )
        .properties(
            title="Average Monthly Spend by Category (Excluding Income and Investments)",
        )
    )
    st.altair_chart(monthly_averages_chart, use_container_width=True)

    # Calculate and display percentage of investments in relation to income
    total_investments = df[df["category"] == "Investments"]["amount"].sum()
    total_income = df[df["category"] == "Income"]["amount"].sum()
    if total_income != 0:
        investments_percentage = (total_investments / total_income) * 100
    else:
        investments_percentage = 0

    st.metric("Investments as % of Income", f"{investments_percentage:.2f}%")


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


@st.cache_data
def process_tsv(file, file_type):
    max_cols = 0
    for line in file:
        num_cols = len(line.decode("ISO-8859-1").split("\t"))
        max_cols = max(max_cols, num_cols)

    file.seek(0)

    column_names = [f"Column_{i}" for i in range(max_cols)]

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
        columns_to_keep = [df.columns[i] for i in [5, 6, 7]]
    elif file_type == "Company Credit":
        columns_to_keep = [df.columns[i] for i in [1, 2, 3]]

    df = df[columns_to_keep]
    df = df.applymap(replace_empty_with_none)
    df = df.dropna(axis=0)
    df = df[1:]
    df.columns = ["date", "description", "amount"]
    try:
        df.date = pd.to_datetime(df.date)
    except ParserError:
        st.warning("Ficheiro Inválido")
        st.stop()
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
    uploaded_file = st.file_uploader("Choose a file", type=["tsv", "xls"])

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
