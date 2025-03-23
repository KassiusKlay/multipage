import streamlit as st
import pandas as pd
import datetime
import altair as alt
import yfinance as yf
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.credentials import Credentials
from degiro_connector.trading.models.account import (
    OverviewRequest,
    UpdateOption,
    UpdateRequest,
)
from degiro_connector.trading.models.transaction import HistoryRequest
from currency_converter import CurrencyConverter


def get_ticker_data(ticker):
    return yf.Ticker(ticker)


def check_credentials():
    try:
        credentials = Credentials(
            int_account=61003450,
            username=st.session_state.username,
            password=st.session_state.password,
            one_time_password=int(st.session_state.one_time_password),
        )
        api = TradingAPI(credentials=credentials)
        api.connect()
        st.session_state.api = api
        return
    except Exception:
        st.warning("Wrong Credentials")
        return


def login():
    with st.form(key="credentials"):
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.text_input("One Time Password", key="one_time_password")
        st.form_submit_button("Login", on_click=check_credentials)


@st.cache_data
def get_account_overview(_api):
    request = OverviewRequest(
        from_date=(
            datetime.date(
                year=2017,
                month=1,
                day=1,
            )
        ),
        to_date=datetime.date.today(),
    )

    return pd.DataFrame(
        api.get_account_overview(
            overview_request=request,
            raw=True,
        )[
            "data"
        ]["cashMovements"]
    )


@st.cache_data
def get_transaction_history(_api):
    return pd.DataFrame(
        _api.get_transactions_history(
            transaction_request=HistoryRequest(
                from_date=datetime.date(year=2017, month=1, day=1),
                to_date=datetime.date.today(),
            ),
            raw=True,
        )["data"]
    )


@st.cache_data
def get_account_update(_api):
    account_update = _api.get_update(
        request_list=[
            UpdateRequest(
                option=UpdateOption.PORTFOLIO,
                last_update=0,
            ),
            UpdateRequest(
                option=UpdateOption.TOTAL_PORTFOLIO,
                last_update=0,
            ),
        ],
        raw=False,
    )
    return account_update


@st.cache_data
def get_products_info(_api, _productsIds):
    return _api.get_products_info(
        product_list=_productsIds,
        raw=True,
    )["data"]


@st.cache_data
def process_splits_data(df):
    df = df.copy()  # Ensure a copy is used to avoid SettingWithCopyWarning
    splits = df.loc[df.transactionTypeId == 101].groupby("date")
    for _, split_df in splits:
        split_factor = (
            split_df.loc[split_df.buysell == "S"].price.iloc[0]
            / split_df.loc[split_df.buysell == "B"].price.iloc[0]
        )
        df.loc[df.date <= split_df.date.iloc[0], "price"] /= split_factor
        df.loc[df.date <= split_df.date.iloc[0], "quantity"] = (
            df.loc[df.date <= split_df.date.iloc[0], "quantity"] * split_factor
        ).astype(
            int
        )  # Ensure dtype compatibility
        df = pd.concat([df, split_df]).drop_duplicates(subset="id", keep=False)
    return df


@st.cache_data
def add_current_portfolio_data(current_portfolio):
    df = pd.DataFrame()
    for symbol in current_portfolio.symbol.unique():
        data = get_ticker_data(symbol)
        df = pd.concat(
            [
                df,
                pd.DataFrame(
                    {
                        "symbol": [symbol],
                        "high52": [data.fast_info["year_high"]],
                        "low52": [data.fast_info["year_low"]],
                        "previousClose": [data.fast_info["previous_close"]],
                    }
                ),
            ],
            ignore_index=True,
        )
    return current_portfolio.merge(df, on="symbol")


@st.cache_data
def get_usd_eur_exchange_rate():
    c = CurrencyConverter()
    return c.convert(1, "USD", "EUR")


def percentage(val):
    if val > 0:
        color = "green"
    elif val < 0:
        color = "red"
    else:
        color = "black"
    return "color: %s" % color


def show_current_portfolio(current_portfolio):
    df = current_portfolio.copy()
    df.plBase = df.plBase.str["EUR"].abs()
    df["profit"] = (df.value - df.plBase) / df.plBase

    df = add_current_portfolio_data(df)
    df["change"] = (df.price - df.previousClose) / df.previousClose
    df["fromHigh52"] = (df.price - df.high52) / df.high52
    df = (
        df[
            [
                "symbol",
                "price",
                "change",
                "high52",
                "low52",
                "fromHigh52",
                "size",
                "plBase",
                "breakEvenPrice",
                "value",
                "profit",
            ]
        ]
        .set_index("symbol")
        .sort_values(by="value", ascending=False)
    )

    styler = (
        df.convert_dtypes()
        .style.map(
            percentage, subset=["profit", "change", "fromHigh52"]
        )  # Updated to use .map instead of .applymap
        .format(
            {
                "profit": "{:+.1%}",
                "change": "{:+.1%}",
                "fromHigh52": "{:+.1%}",
            },
            precision=2,
        )
    )
    st.write(styler)


def show_account_movement(account_df):
    deposits = account_df[
        (account_df.description.str.contains("Withdrawal"))
        | (account_df.description.str.contains("dep", case=False))
    ].copy()
    deposits.description = deposits.description.where(
        deposits.description.str.contains("Withdrawal"), "Deposits"
    )
    deposits.description = deposits.description.mask(
        deposits.description.str.contains("Withdrawal"), "Withdrawal"
    )

    bar = (
        alt.Chart(deposits)
        .mark_bar()
        .encode(
            x=alt.X(
                "description", axis=alt.Axis(title=None, labels=False, ticks=False)
            ),
            y="sum(change)",
            color="description",
            column="year(date)",
        )
    )
    st.altair_chart(bar)


@st.cache_data
def get_historical_data(ticker):
    historical_data = yf.download(ticker)
    historical_data.columns = historical_data.columns.droplevel(1)
    historical_data = historical_data["Close"].reset_index()
    if historical_data.empty:
        st.warning("Sem dados")
        st.stop()
    return historical_data


@st.cache_data
def get_comparing_df(ticker, start_date):
    df = get_ticker_data(ticker).history(start=start_date)["Close"].reset_index()
    df.Date = df.Date.dt.date
    df.Date = pd.to_datetime(df.Date, utc=True)
    return df


def show_transaction_history(transaction_df):
    tickers = transaction_df.symbol.sort_values().unique().tolist()
    tsla_index = tickers.index("TSLA")

    ticker = st.selectbox(
        "Select Ticker",
        tickers,
        tsla_index,
    )

    historical_data = get_historical_data(ticker)

    df = transaction_df[transaction_df.symbol == ticker]
    df = process_splits_data(df)
    df.date = pd.to_datetime(df.date)

    today = historical_data.iloc[-1].Close
    cur = get_usd_eur_exchange_rate()
    df["PL"] = df.quantity * today * cur + df.totalPlusAllFeesInBaseCurrency

    window = 7
    list_of_min = []
    list_of_max = []
    for i, row in df.iterrows():
        start_date = (row.date - pd.Timedelta(days=window)).date()
        end_date = (row.date + pd.Timedelta(days=window)).date()
        subset_df = historical_data[
            (historical_data.Date.dt.date > start_date)
            & (historical_data.Date.dt.date < end_date)
        ].Close
        list_of_min.append(subset_df.min())
        list_of_max.append(subset_df.max())
    df = df.assign(min_price=list_of_min, max_price=list_of_max)
    df["pct_min"] = df[["min_price", "price"]].pct_change(axis=1)["price"]
    df["pct_max"] = df[["price", "max_price"]].pct_change(axis=1)["max_price"]
    df["Best"] = df.PL + df.PL * df.pct_min
    df["Worst"] = df.PL - df.PL * df.pct_max
    df["ideal"] = df.PL + df.PL * df.pct_min
    pct_pl = df.PL.sum() / df.totalPlusAllFeesInBaseCurrency.abs().sum()
    best = df.PL.sum() - df.Best.sum()
    worst = df.PL.sum() - df.Worst.sum()
    cols = st.columns(3)
    cols[0].metric("Current PL", f"{int(df.PL.sum())}€", f"{pct_pl:.0%}")
    cols[1].metric("Vs. Best Investor", f"{int(df.Best.sum())}€", f"{int(best)}€")
    cols[2].metric("Vs. Worst Investor", f"{int(df.Worst.sum())}€", f"{int(worst)}€")

    df.totalPlusFeeInBaseCurrency = df.totalPlusFeeInBaseCurrency.abs()
    line = alt.Chart(historical_data).mark_line().encode(x="Date:T", y="Close:Q")
    circle = (
        alt.Chart(df)
        .mark_circle()
        .encode(
            x=alt.X("date:T", title="Date"),
            y=alt.Y("price:Q", title="Price"),
            size=alt.Size("totalPlusFeeInBaseCurrency", legend=None),
            tooltip=["quantity", "totalPlusFeeInBaseCurrency"],
            color=alt.Color(
                "buysell",
                legend=alt.Legend(title="Buy/Sell"),
                scale=alt.Scale(scheme="dark2"),
            ),
        )
        .interactive()
    )
    st.altair_chart(line + circle, use_container_width=True)


def get_portfolio_df(info):
    columns = set()
    for item in info:
        for val in item["value"]:
            columns.add(val["name"])
    data = []
    for item in info:
        row = {}
        for col in columns:
            for val in item["value"]:
                if val["name"] == col:
                    row[col] = val.get("value", None)
                    break
            else:
                row[col] = None
        data.append(row)
    df = pd.DataFrame(data, columns=list(columns))
    return df


def show_potential_portfolio(transaction_df, portfolio_value):
    df = transaction_df.copy()
    df["date"] = df["date"].str[:10]
    df["date"] = pd.to_datetime(df["date"], utc=True)

    final = pd.DataFrame()
    for symbol in df.symbol.unique():
        _ = process_splits_data(df[df.symbol == symbol])
        final = pd.concat([final, _], ignore_index=True)

    i = st.text_input("Select a Ticker").upper()
    if not i:
        st.stop()

    cols = st.columns(3)
    for col_num, ticker in enumerate(["SPY", "QQQ", i]):
        comparing_df = get_comparing_df(ticker, final.date.min())
        df = final.merge(comparing_df, left_on="date", right_on="Date", how="left")
        df["Alt_Shares"] = df.apply(lambda row: -row["total"] / row["Close"], axis=1)
        total_shares = df["Alt_Shares"].sum()
        current_price = comparing_df.iloc[-1]["Close"]
        current_value = total_shares * current_price
        cols[col_num].metric(
            ticker, f"{current_value:.0f}€", f"{portfolio_value - current_value:.0f}€"
        )


logout = st.sidebar.button("logout")
if logout:
    try:
        del st.session_state.api
    except AttributeError:
        pass
    st.cache_data.clear()

if "api" not in st.session_state:
    login()
    st.stop()

api = st.session_state.api
account_df = get_account_overview(api)
transaction_df = get_transaction_history(api)
products_info = get_products_info(api, transaction_df.productId.unique().tolist())
transaction_df.insert(
    loc=3,
    column="symbol",
    value=transaction_df.productId.apply(lambda x: products_info[str(x)]["symbol"]),
)

account_update = get_account_update(api)
portfolio_df = get_portfolio_df(account_update.portfolio["value"])
total_portfolio_df = pd.DataFrame(account_update.total_portfolio["value"])

current_portfolio = portfolio_df[
    (portfolio_df["size"] > 0) & (portfolio_df.positionType == "PRODUCT")
].copy()
current_portfolio["symbol"] = current_portfolio.id.apply(
    lambda x: products_info[str(x)]["symbol"]
)
total_portfolio_df = total_portfolio_df.drop(columns=["isAdded"])
total_portfolio_df = total_portfolio_df.set_index("name")
total_portfolio_df = total_portfolio_df.T
total_deposits = total_portfolio_df.totalDepositWithdrawal.squeeze()
free_cash = total_portfolio_df.totalCash.squeeze()
portfolio_value = portfolio_df.value.sum()
total_fees = transaction_df.totalFeesInBaseCurrency.abs().sum()


st.write("Total Deposits:", total_deposits)
st.write("Free Cash:", free_cash)
st.write("Portfolio value:", int(portfolio_value))
st.write("Total fees:", int(total_fees))

tab1, tab2, tab3, tab4 = st.tabs(
    [
        "Current Portfolio",
        "Account Movement",
        "Transaction History",
        "Potential Portfolio",
    ]
)

with tab1:
    show_current_portfolio(current_portfolio)
with tab2:
    show_account_movement(account_df)
with tab3:
    show_transaction_history(transaction_df)
with tab4:
    show_potential_portfolio(
        transaction_df[
            transaction_df["symbol"].isin(current_portfolio["symbol"].unique())
        ],
        int(portfolio_value),
    )
