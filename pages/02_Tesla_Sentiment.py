import yfinance as yf
import streamlit as st
import pandas as pd
import altair as alt
from sqlalchemy import create_engine
import os

st.set_page_config(layout="wide")

START_DATE = "2010-01-01"


@st.experimental_singleton
def init_engine():
    try:
        engine = create_engine(
            f"postgresql://"
            f'{st.secrets["postgres"]["user"]}:'
            f'{st.secrets["postgres"]["password"]}@'
            f'{st.secrets["postgres"]["host"]}:'
            f'{st.secrets["postgres"]["port"]}/'
            f'{st.secrets["postgres"]["dbname"]}',
        )
    except FileNotFoundError:
        DB_USER = os.environ.get("DB_USER")
        DB_PSWD = os.environ.get("DB_PSWD")
        DB_HOST = os.environ.get("DB_HOST")
        DB_PORT = os.environ.get("DB_PORT")
        DB_NAME = os.environ.get("DB_NAME")
        engine = create_engine(
            f"postgresql://{DB_USER}:{DB_PSWD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"
        )
    return engine


@st.experimental_memo
def get_ticker_data(ticker):
    return yf.Ticker(ticker)


engine = init_engine()
sentiment_df = pd.read_sql(
    """
SELECT date, positive, negative, neutral FROM tesla_news""",
    engine,
)
sentiment_df["sentiment"] = sentiment_df.positive - sentiment_df.negative * 5
sentiment_df = sentiment_df.groupby("date").agg({"sentiment": "sum"})
sentiment_df.sentiment = sentiment_df.sentiment.cumsum()

data = get_ticker_data("TSLA")
df = data.history(start=START_DATE)["Close"]

stock = (
    alt.Chart(df.reset_index())
    .mark_line()
    .encode(
        x="Date:T",
        y="Close:Q",
    )
)

sentiment = (
    alt.Chart(sentiment_df.reset_index())
    .mark_line(color="orange")
    .encode(
        x="date:T",
        y="sentiment:Q",
    )
)

layer = alt.layer(stock, sentiment).resolve_scale(y="independent")

st.altair_chart(layer, use_container_width=True)
