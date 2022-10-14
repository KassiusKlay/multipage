import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import hashlib
import requests
from datetime import datetime
from meteostat import Point, Daily
import altair as alt

st.set_page_config(layout="wide")
user_hex = (
    "d97d0a1803e85af46fa24716ac627425afc9a46b95e643527d2a8b72dcb1d2d852fe61cbbe"
    "094e0d6e3a7d491baec7ec68e9d7d6d102d5b6c629769993a056f1"
)
city_id = "2267057"
lat = "38.7167"
lon = "-9.1333"
API_key = "8133cd847f23b2c79eec9f5661892669"
weather_url = f"http://api.openweathermap.org/data/2.5/forecast?id={city_id}&appid={API_key}&units=metric"
data = requests.get(weather_url).json()
# st.write(data)


@st.experimental_singleton
def init_engine():
    return create_engine(
        f"postgresql://"
        f'{st.secrets["Yasai"]["user"]}:'
        f'{st.secrets["Yasai"]["password"]}@'
        f'{st.secrets["Yasai"]["host"]}:'
        f'{st.secrets["Yasai"]["port"]}/'
        f'{st.secrets["Yasai"]["dbname"]}',
    )


engine = init_engine()


def check_credentials():
    if (
        not st.session_state.username
        or not st.session_state.password
        or hashlib.sha512(st.session_state.username.encode()).hexdigest() != user_hex
        or st.secrets[st.session_state.username] != st.session_state.password
    ):
        st.warning("Tente novamente")
    else:
        st.session_state.yasai = True


def login():
    with st.form("login"):
        st.text_input("Username", key="username")
        st.text_input("Password", key="password", type="password")
        st.form_submit_button("Login", on_click=check_credentials)


def kitch_venda_de_items():
    file = st.file_uploader("Upload CSV", ["csv"], False, key="upload_kitch_items")
    if file:
        df = pd.read_csv(file)
        df = df.iloc[:, 1:3]
        df.columns = ["name", "count"]
        df = df[["name", "count"]]
        df["daily_average"] = df["count"] / 7
        st.table(df)


def upload_kitch():
    files = st.file_uploader("Upload CSV", ["csv"], True, key="upload_kitch")
    for file in files:
        df = pd.read_csv(file)
        df.createdAt = pd.to_datetime(df.createdAt.str[:10])
        df.columns = [
            "date",
            "channel",
            "ticket_id",
            "order_id",
            "delivery_partner",
            "sales",
            "discounts",
            "delivery_fees",
            "total",
        ]
        stored_df = pd.read_sql(
            "SELECT * FROM yasai_kitch", engine, index_col="id", parse_dates="date"
        )
        df = pd.concat([stored_df, stored_df, df]).drop_duplicates(keep=False)
        if not df.empty:
            df.to_sql("yasai_kitch", engine, if_exists="append", index=False)


def kitch_show_data():
    df = pd.read_sql(
        "SELECT * FROM yasai_kitch", engine, index_col="id", parse_dates="date"
    )
    lisbon = Point(38.7167, -9.1333)

    data = Daily(lisbon, df.date.min(), df.date.max())
    data = data.fetch()

    df = df.groupby(pd.Grouper(key="date", freq="D")).agg(
        {"channel": "count", "sales": "sum"}
    )
    df = df.merge(data, left_index=True, right_index=True)
    df["weekday"] = df.index.weekday
    df["day"] = df.index.day
    df.drop(["snow", "tsun"], axis=1, inplace=True)
    df.rename(columns={"channel": "orders"}, inplace=True)

    st.write(df)
    st.write(df.corr()["sales"])
    weekly_sales = df.groupby(pd.Grouper(level="date", freq="W")).agg({"sales": "sum"})
    chart = (
        alt.Chart(weekly_sales.reset_index())
        .mark_bar()
        .encode(
            x="date",
            y="sales",
        )
    )
    st.altair_chart(chart)


if "yasai" not in st.session_state:
    login()
    st.stop()


st.title("YASAI")
option = st.sidebar.radio(
    "option",
    ["Ver Dados", "Venda de Items Por Data", "Carregar Ficheiros"],
    label_visibility="hidden",
)

if option == "Ver Dados":
    kitch_show_data()
elif option == "Venda de Items por Data":
    kitch_venda_de_items()
elif option == "Carregar Ficheiros":
    upload_kitch()
