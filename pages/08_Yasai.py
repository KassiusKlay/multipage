import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import hashlib

st.set_page_config(layout="wide")
user_hex = (
    "d97d0a1803e85af46fa24716ac627425afc9a46b95e643527d2a8b72dcb1d2d852fe61cbbe"
    "094e0d6e3a7d491baec7ec68e9d7d6d102d5b6c629769993a056f1"
)


@st.experimental_singleton
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


if "yasai" not in st.session_state:
    login()
    st.stop()

st.write("passou")
