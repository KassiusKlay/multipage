import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import hashlib
from PyPDF2 import PdfReader
import re


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


def process_pdf_rota(text):
    items = re.findall(r"W\d{5}.*?(?=€ W)", text)
    df = pd.DataFrame()
    for item in items:
        codigo = re.search(r"W\d{5}", item).group()
        produto = re.search(r"W\d{5} (.*)?(?= \()", item).groups(0)[0]
        peso = re.search(r"\d,\d{3}Gr", item).group()[0]
        unidade = re.search(r"\d Uni", item).group()[0]
        preco_unidade = (
            re.search(r"\d Uni. ([0-9,]+)", item).groups(0)[0].replace(",", ".")
        )
        iva = re.search(r"€ \d+%", item).group()[2:-1]
        row = {
            "codigo": codigo,
            "produto": produto,
            "peso": int(peso),
            "unidade": int(unidade),
            "preco_unidade": float(preco_unidade),
            "iva": int(iva),
        }
        df = pd.concat(
            [df, pd.DataFrame.from_records(row, index=[0])], ignore_index=True
        )
    df["nr_fatura"] = re.search(r"\w{2} \w{3}\/\d{4}", text).group()
    df["data"] = pd.Timestamp(
        re.search(r"Data de Emissão: (\d{2}-\d{2}-\d{4})", text).groups(0)[0]
    )
    df["fornecedor"] = "Rota das Índias"
    return df


def process_pdf_bluespring(text):
    nr_fatura = re.search(r"FA \d{4}\/\d{3}", text).group()
    data = pd.Timestamp(
        re.search(r"\d{2}\/\d{2}\/\d{4}(\d{2}\/\d{2}\/\d{4})", text).groups(0)[0]
    )
    item = re.search(r"IVA (.*?) Blue", text).groups(0)[0]
    produto = re.search(r".+?(?= \d)", item).group()
    numeros = re.findall(r"\d+,?\d+", item)
    unidade = int(float(numeros[0].replace(",", ".")))
    preco_unidade = float(numeros[1].replace(",", "."))
    iva = int(float(numeros[3].replace(",", ".")))
    df = pd.DataFrame(
        {
            "data": data,
            "nr_fatura": nr_fatura,
            "codigo": None,
            "produto": produto,
            "unidade": unidade,
            "preco_unidade": preco_unidade,
            "iva": iva,
            "peso": None,
            "fornecedor": "BlueSpring",
        },
        index=[0],
    )
    return df


def process_pdf_kitch(text):
    nr_fatura = re.search("FR.*?(?= Original)", text).group()
    data = pd.Timestamp(re.search(r"\d{4}-\d{2}-\d{2}", text).group())
    item = re.search(r"AT (.*)?(?= Kitch,)", text).groups(0)[0]
    produto = re.search(r".+?(?= €)", item).group()
    preco_unidade = float(re.search(r"\d.+?(?= Uni)", item).group().replace(",", "."))
    unidade = int(re.search(r"Uni (\d)", item).groups(0)[0])
    iva = int(re.search(r"(\d+)%", item).groups(0)[0])
    df = pd.DataFrame(
        {
            "data": data,
            "nr_fatura": nr_fatura,
            "codigo": None,
            "produto": produto,
            "unidade": unidade,
            "preco_unidade": preco_unidade,
            "iva": iva,
            "peso": None,
            "fornecedor": "Kitch",
        },
        index=[0],
    )
    return df


@st.experimental_memo
def get_stored_data():
    return pd.read_sql(
        "SELECT * FROM yasai_faturas", engine, parse_dates=["data"], index_col="id"
    )


def upload_files():
    stored_df = get_stored_data()
    uploaded_files = st.file_uploader(
        "",
        type="pdf",
        accept_multiple_files=True,
    )
    df = pd.DataFrame()
    if uploaded_files:
        for file in uploaded_files:
            reader = PdfReader(file)
            page = reader.pages[0]
            text = page.extract_text().replace("\n", " ")
            if "Quinta" in text.split()[0]:
                df = pd.concat([df, process_pdf_rota(text)])
            elif "bluespring" in text:
                df = pd.concat([df, process_pdf_bluespring(text)])
            elif "Kitch" in text.split()[0]:
                df = pd.concat([df, process_pdf_kitch(text)])
        df = pd.concat([stored_df, stored_df, df]).drop_duplicates(keep=False)
        if not df.empty:
            df.to_sql("yasai_faturas", engine, if_exists="append", index=False)
            st.experimental_memo.clear()
            st.success("Faturas guardadas")
        else:
            st.info("Sem faturas novas")


def main_page():
    stored_df = get_stored_data()
    st.write(stored_df)


if "yasai" not in st.session_state:
    login()
    st.stop()


option = st.sidebar.radio("", ["Ver Dados", "Carregar Ficheiros"])

if option == "Ver Dados":
    main_page()
else:
    upload_files()
