import yfinance as yf
import streamlit as st
import pandas as pd
import altair as alt
import datetime

st.set_page_config(layout="wide")

START_DATE = "2010-01-01"


def get_ticker_data(ticker):
    return yf.Ticker(ticker)


@st.cache_data
def get_drop_df(df, sp500):
    maxes = df.groupby(pd.Grouper(freq="Y")).max()
    while any(maxes.pct_change() < 0):
        maxes = maxes[~(maxes.pct_change() < 0)]
    years = maxes.index.year.unique()
    drop_df = pd.DataFrame(
        columns=[
            "start_idx",
            "min_idx",
            "recover_idx",
            "end_idx",
        ]
    )

    for i in range(len(years) - 1):
        start_idx = df[str(years[i])].idxmax()
        end_idx = df[str(years[i + 1])].idxmax()
        min_idx = df[start_idx:end_idx].idxmin()
        if df[start_idx:min_idx].max() > df[start_idx].max():
            start_idx = df[start_idx:min_idx].idxmax()
            if i != 0:
                drop_df.loc[i - 1, "end_idx"] = start_idx
        recover_idx = df[min_idx:end_idx][df[min_idx:end_idx] > df[start_idx]].index[0]
        drop_df.loc[len(drop_df.index)] = [
            start_idx,
            min_idx,
            recover_idx,
            end_idx,
        ]

    max_idx = df.idxmax()
    min_idx = drop_df.loc[len(drop_df.index)] = [
        df.idxmax(),
        df[max_idx:].idxmin(),
        None,
        df.index.max(),
    ]

    drop_df["price_start"] = df[drop_df.start_idx].reset_index(drop=True)
    drop_df["price_min"] = df[drop_df.min_idx].reset_index(drop=True)
    drop_df["price_end"] = df[drop_df.end_idx].reset_index(drop=True)
    drop_df["pct_drop"] = drop_df[["price_start", "price_min"]].pct_change(
        axis="columns"
    )["price_min"]
    drop_df["pct_gain"] = drop_df[["price_min", "price_end"]].pct_change(
        axis="columns"
    )["price_end"]
    sp500_min = sp500[drop_df.min_idx].reset_index(drop=True)
    sp500_max = sp500[drop_df.start_idx].reset_index(drop=True)
    sp500_change = (sp500_min - sp500_max) / sp500_max
    drop_df["sp500_change"] = sp500_change

    drop_df["days_to_min"] = (drop_df.min_idx - drop_df.start_idx).apply(
        lambda x: x.days
    )
    drop_df["days_to_recover"] = (
        (drop_df.recover_idx - drop_df.min_idx)
        .apply(lambda x: x.days)
        .fillna(0)
        .astype(int)
    )
    drop_df["days_to_new_peak_from_bottom"] = (drop_df.end_idx - drop_df.min_idx).apply(
        lambda x: x.days
    )
    drop_df["days_to_new_peak_from_previous"] = (
        drop_df.end_idx - drop_df.start_idx
    ).apply(lambda x: x.days)

    drop_df = drop_df[drop_df.pct_drop < -0.1]
    return drop_df


ticker = st.text_input("TICKER").upper()
start_date = st.date_input(
    "DATA INICIO",
    value=datetime.datetime.strptime(START_DATE, "%Y-%m-%d"),
    min_value=datetime.datetime.strptime("1993-01-29", "%Y-%m-%d"),
    max_value=datetime.date.today(),
)
if start_date < datetime.datetime.strptime("1993-01-29", "%Y-%m-%d").date():
    st.warning("Data invalida. Dados a partir de 1993-1-29")
    st.stop()

if not ticker:
    st.stop()
data = get_ticker_data(ticker)
df = data.history(start=start_date)["Close"]
if df.empty:
    st.warning("Escolha um TICKER válido")
    st.stop()

sp500 = get_ticker_data("SPY").history(start=start_date).loc[df.index.min() :, "Close"]

drop_df = get_drop_df(df, sp500)

layers = alt.layer()
layers += (
    alt.Chart(df.reset_index())
    .mark_line()
    .encode(
        x=alt.X("Date:T", axis=alt.Axis(title="Date"), scale=alt.Scale(padding=2)),
        y=alt.Y("Close:Q", axis=alt.Axis(title="Close")),
    )
)
for _, row in drop_df.iterrows():
    period_df = df[row.start_idx : row.min_idx].reset_index()
    mid_point = period_df.iloc[round(len(period_df) / 2)]
    drop_line = (
        alt.Chart(period_df).mark_line(color="orange").encode(x="Date:T", y="Close:Q")
    )

    drop_text = (
        alt.Chart(
            pd.DataFrame({"date": [mid_point.Date], "close": [period_df.Close.max()]})
        )
        .mark_text(dy=-20, color="orange", size=20)
        .encode(
            x="date",
            y="close",
            text=alt.value(f"{row.pct_drop:.0%}"),
        )
    )
    layers += drop_line + drop_text


# st.title(f"{ticker} ({data.fast_info['longName']})")

chart = (
    layers.configure_view(stroke=None)
    .configure_axisX(tickCount="year")
    .configure_axis(title=None, grid=False)
)
st.altair_chart(chart, use_container_width=True)

st.write(
    drop_df[:-1]
    .describe()
    .loc[
        ["min", "max", "mean"],
        [
            "pct_drop",
            "pct_gain",
            "sp500_change",
            "days_to_min",
            "days_to_recover",
            "days_to_new_peak_from_bottom",
            "days_to_new_peak_from_previous",
        ],
    ]
)


sp500_pct = sp500 / sp500.iat[0] - 1
sp500_pct = pd.concat(
    [sp500_pct, pd.Series("SP500", index=sp500_pct.index)],
    axis=1,
    keys=["Close", "Ticker"],
)
ticker_pct = df / df.iat[0] - 1
ticker_pct = pd.concat(
    [ticker_pct, pd.Series(f"{ticker}", index=df.index)],
    axis=1,
    keys=["Close", "Ticker"],
)
combined_pct = pd.concat([sp500_pct, ticker_pct], axis=0)

line = (
    alt.Chart(combined_pct.reset_index())
    .mark_line()
    .encode(
        x=alt.X("Date:T", axis=alt.Axis(tickCount="year"), scale=alt.Scale(padding=2)),
        y=alt.Y("Close:Q", title="Percentage Change", axis=alt.Axis(format=".0%")),
        color="Ticker",
        tooltip=alt.Text("Close:Q", format=".0%"),
    )
)

chart = line.configure_view(stroke=None).configure_axis(grid=False)
st.title(f"{ticker} vs SP500")
st.altair_chart(chart, use_container_width=True)
