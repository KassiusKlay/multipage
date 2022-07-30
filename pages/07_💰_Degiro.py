import streamlit as st
import pandas as pd
import datetime
import altair as alt
import yfinance as yf
import degiro_connector.core.helpers.pb_handler as pb_handler
from degiro_connector.trading.api import API as TradingAPI
from degiro_connector.trading.models.trading_pb2 import (
    Credentials,
    AccountOverview,
    TransactionsHistory,
    ProductsInfo,
    Update,
)
from degiro_connector.quotecast.api import API as QuotecastAPI
from degiro_connector.quotecast.models.quotecast_pb2 import Quotecast

st.set_page_config(layout="wide")


@st.experimental_memo
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
        st.session_state.api = TradingAPI(credentials=credentials)
        st.session_state.api.connect()
    except Exception:
        st.warning("Wrong Credentials")


def login():
    with st.form(key="credentials"):
        st.text_input("Username", key="username")
        st.text_input("Password", type="password", key="password")
        st.text_input("One Time Password", key="one_time_password")
        st.form_submit_button("Login", on_click=check_credentials)


@st.experimental_memo
def get_account_overview(_api):
    today = datetime.date.today()
    from_date = AccountOverview.Request.Date(
        year=2017,
        month=1,
        day=1,
    )
    to_date = AccountOverview.Request.Date(
        year=today.year, month=today.month, day=today.day
    )

    request = AccountOverview.Request(
        from_date=from_date,
        to_date=to_date,
    )

    return pd.DataFrame(
        api.get_account_overview(request=request, raw=True,)[
            "data"
        ]["cashMovements"]
    )


@st.experimental_memo
def get_transaction_history(_api):
    today = datetime.date.today()
    from_date = TransactionsHistory.Request.Date(
        year=2017,
        month=1,
        day=1,
    )
    to_date = TransactionsHistory.Request.Date(
        year=today.year,
        month=today.month,
        day=today.day,
    )
    request = TransactionsHistory.Request(
        from_date=from_date,
        to_date=to_date,
    )

    return pd.DataFrame(
        _api.get_transactions_history(
            request=request,
            raw=True,
        )["data"]
    )


@st.experimental_memo
def get_update_info(_api):
    request_list = Update.RequestList()
    request_list.values.extend(
        [
            Update.Request(option=Update.Option.PORTFOLIO, last_updated=0),
            Update.Request(option=Update.Option.TOTALPORTFOLIO, last_updated=0),
        ]
    )

    update = api.get_update(request_list=request_list, raw=False)
    update_dict = pb_handler.message_to_dict(message=update)
    return update_dict


@st.experimental_memo
def get_product_info(_api, _productsId):
    request = ProductsInfo.Request()
    request.products.extend(_productsId)

    return _api.get_products_info(
        request=request,
        raw=True,
    )["data"]


@st.experimental_memo
def process_splits_data(df):
    splits = df.loc[df.transactionTypeId == 101].groupby("date")
    for split, split_df in splits:
        split_factor = (
            split_df.loc[split_df.buysell == "S"].price.iloc[0]
            / split_df.loc[split_df.buysell == "B"].price.iloc[0]
        )
        df.price = df.price.where(
            ~(df.date < split_df.date.iloc[0]), other=(df.price / split_factor)
        )
        df.quantity = df.quantity.where(
            ~(df.date < split_df.date.iloc[0]), other=(df.quantity * split_factor)
        )
        df = df.merge(split_df, how="outer", indicator=True).loc[
            lambda x: x["_merge"] == "left_only"
        ]
    df = df.drop(df.columns[-1], axis=1)
    return df


@st.experimental_memo
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
                        "high52": [data.info["fiftyTwoWeekHigh"]],
                        "low52": [data.info["fiftyTwoWeekLow"]],
                        "previousClose": [data.info["previousClose"]],
                    }
                ),
            ],
            ignore_index=True,
        )
    return current_portfolio.merge(df, on="symbol")


def percentage(val):
    if val > 0:
        color = "green"
    elif val < 0:
        color = "red"
    else:
        color = "black"
    return "color: %s" % color


def show_current_portfolio(portfolio_df, products_info):
    current_portfolio = portfolio_df[
        (portfolio_df["size"] > 0) & (portfolio_df.positionType == "PRODUCT")
    ]
    current_portfolio["symbol"] = current_portfolio.id.apply(
        lambda x: products_info[str(x)]["symbol"]
    )

    current_portfolio.plBase = current_portfolio.plBase.str["EUR"].abs()
    current_portfolio["profit"] = (
        current_portfolio.value - current_portfolio.plBase
    ) / current_portfolio.plBase

    current_portfolio = add_current_portfolio_data(current_portfolio)
    current_portfolio["change"] = (
        current_portfolio.price - current_portfolio.previousClose
    ) / current_portfolio.previousClose
    current_portfolio["fromHigh52"] = (
        current_portfolio.price - current_portfolio.high52
    ) / current_portfolio.high52
    current_portfolio = (
        current_portfolio[
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
        current_portfolio.convert_dtypes()
        .style.applymap(percentage, subset=["profit", "change", "fromHigh52"])
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
    ]
    deposits.description = deposits.description.where(
        deposits.description == "Withdrawal", "Deposits"
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


def show_transaction_history(transaction_df):
    tickers = transaction_df.symbol.sort_values().unique().tolist()
    tsla_index = tickers.index("TSLA")

    ticker = st.selectbox(
        "Select Ticker",
        tickers,
        tsla_index,
    )

    df = transaction_df[transaction_df.symbol == ticker]
    df = process_splits_data(df)
    historical_data = yf.download(ticker)["Close"].reset_index()
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


logout = st.sidebar.button("logout")
if logout:
    try:
        del st.session_state.api
    except AttributeError:
        pass

if "api" not in st.session_state:
    login()
    st.stop()

api = st.session_state.api

account_df = get_account_overview(api)

transaction_df = get_transaction_history(api)
products_info = get_product_info(api, transaction_df.productId.unique())
transaction_df.insert(
    loc=3,
    column="symbol",
    value=transaction_df.productId.apply(lambda x: products_info[str(x)]["symbol"]),
)

update_dict = get_update_info(api)
if "portfolio" in update_dict:
    portfolio_df = pd.DataFrame(update_dict["portfolio"]["values"])
if "total_portfolio" in update_dict:
    total_portfolio_df = pd.DataFrame(update_dict["total_portfolio"]["values"])


total_deposits = total_portfolio_df.loc["EUR"].totalDepositWithdrawal
free_cash = total_portfolio_df.loc["EUR"].totalCash
portfolio_value = portfolio_df.value.sum()


st.write("Total Deposits:", total_deposits)
st.write("Free Cash:", free_cash)
st.write("Portfolio value:", int(portfolio_value))

tab1, tab2, tab3 = st.tabs(
    ["Current Portfolio", "Account Movement", "Transaction History"]
)

with tab1:
    show_current_portfolio(portfolio_df, products_info)
with tab2:
    show_account_movement(account_df)
with tab3:
    show_transaction_history(transaction_df)
