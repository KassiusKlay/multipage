import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import hashlib
from PyPDF2 import PdfReader
import re
import datetime


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


def process_pdf_weat(text):
    nr_fatura = re.search(r"\d{4}\/\d+", text).group()
    data = pd.Timestamp(
        re.search(r"Data de Emissão (\d{4}-\d{2}-\d{2})", text).groups(0)[0]
    )
    item = re.search(r"TOTAL (.*) Resumo", text).groups(0)[0]
    produto = re.search("[A-Z].*", item).group()
    preco_unidade = float(
        re.search(r" (.*?) ", item).group().replace(".", "").replace(",", ".")
    )
    unidade = int(re.search(r"(.*?).", item).group())
    iva = int(re.findall(r"(.*?) ", item)[3].split(".")[0])
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
            "fornecedor": "Weat",
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
            elif "WGH, LDA" in text:
                df = pd.concat([df, process_pdf_weat(text)])
        df = pd.concat([stored_df, stored_df, df]).drop_duplicates(keep=False)
        if not df.empty:
            df.to_sql("yasai_faturas", engine, if_exists="append", index=False)
            st.experimental_memo.clear()
            st.success("Faturas guardadas")
        else:
            st.info("Sem faturas novas")


def manual_input():
    stored_df = get_stored_data()
    cols = st.columns(4)
    linhas = cols[0].number_input("Linhas", 1, step=1)
    data = cols[1].date_input("Data", value=datetime.date.today())
    fornecedores = stored_df.fornecedor.sort_values().unique().tolist()
    fornecedores.insert(0, "Novo")
    produtos = stored_df.produto.sort_values().unique().tolist()
    produtos.insert(0, "Novo")
    fornecedor = cols[2].selectbox("Fornecedor", fornecedores)
    if fornecedor == "Novo":
        fornecedor = cols[3].text_input("Novo fornecedor")
    if not fornecedor:
        st.warning("Inserir fornecedor")
        st.stop()
    df = pd.DataFrame()
    for i in range(int(linhas)):
        cols = st.columns([1, 2, 0.5, 0.5, 0.5, 0.5])
        codigo = cols[0].text_input("Codigo", key=f"codigo_{i}")
        produto = cols[1].selectbox("Produto", produtos, key=f"produto_{i}")
        if produto == "Novo":
            produto = cols[1].text_input("Novo produto", key=f"novo_produto_{i}")
        peso = cols[2].number_input("Peso (kg)", min_value=0.0, key=f"peso_{i}")
        unidade = cols[3].number_input("Unidade", min_value=0, key=f"unidade_{i}")
        preco_unidade = cols[4].number_input(
            "Preco", min_value=0.0, key=f"preco_unidade_{i}"
        )
        iva = cols[5].selectbox("IVA", options=[0, 6, 23], key=f"iva_{i}")
        if not unidade or not produto:
            st.warning("Linha incompleta")
            st.stop()
        df = pd.concat(
            [
                df,
                pd.DataFrame.from_records(
                    {
                        "codigo": codigo,
                        "produto": produto,
                        "peso": peso,
                        "unidade": unidade,
                        "preco_unidade": preco_unidade,
                        "iva": iva,
                    },
                    index=[0],
                ),
            ]
        )
    df = df.assign(data=data, fornecedor=fornecedor)
    st.write(df)


def main_page():
    stored_df = get_stored_data()
    st.write(stored_df)


if "yasai" not in st.session_state:
    login()
    st.stop()


option = st.sidebar.radio(
    "", ["Ver Dados", "Carregar Ficheiros", "Introduzir Manualmente"]
)

if option == "Ver Dados":
    main_page()
elif option == "Carregar Ficheiros":
    upload_files()
elif option == "Introduzir Manualmente":
    manual_input()
