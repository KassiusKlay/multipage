import streamlit as st
import pandas as pd
from sqlalchemy import create_engine
import hashlib
from PyPDF2 import PdfReader
import re
import datetime
from functools import reduce


st.set_page_config(layout="wide")
user_hex = (
    "d97d0a1803e85af46fa24716ac627425afc9a46b95e643527d2a8b72dcb1d2d852fe61cbbe"
    "094e0d6e3a7d491baec7ec68e9d7d6d102d5b6c629769993a056f1"
)


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


def process_pdf_rota(text):
    items = re.findall(r"W\d+.*?€(?= [A-Z])", text)
    df = pd.DataFrame()
    for item in items:
        codigo = re.search(r"W\d{5}", item).group()
        produto = re.search(r"W\d{5} (.*)?(?= \()", item).groups(0)[0]
        peso = int(re.search(r"\d,\d{3}Gr", item).group()[0])
        unidade = int(re.search(r"\d Uni", item).group()[0])
        preco_sem_iva = float(
            re.search(r"% (\d+,\d+)", item).groups(0)[0].replace(",", ".")
        )
        iva = int(re.search(r"€ \d+%", item).group()[2:-1])
        row = {
            "codigo": codigo,
            "produto": produto,
            "peso": peso,
            "unidade": unidade,
            "preco_sem_iva": preco_sem_iva,
            "iva": iva,
        }
        df = pd.concat(
            [df, pd.DataFrame.from_records(row, index=[0])], ignore_index=True
        )
    df["nr_fatura"] = re.search(r"Fatura-Recibo N.º (.*) Data de Emissão", text).groups(
        0
    )[0]
    df["data"] = pd.Timestamp(
        re.search(r"Data de Emissão: (\d{2}-\d{2}-\d{4})", text).groups(0)[0]
    )
    df["fornecedor"] = "Rota das Índias"
    df["descricao"] = "Comida"
    return df


def process_pdf_bluespring(text):
    nr_fatura = re.search(r"Factura (.*)?(?= Pr\.)", text).groups(0)[0]
    data = pd.Timestamp(
        re.search(r"\d{2}\/\d{2}\/\d{4}(\d{2}\/\d{2}\/\d{4})", text).groups(0)[0]
    )
    item = re.search(r"IVA (.*?) Blue", text).groups(0)[0]
    produto = re.search(r".+?(?= \d)", item).group()
    numeros = re.findall(r"\d+,?\d+", item)
    unidade = int(float(numeros[0].replace(",", ".")))
    preco_sem_iva = float(numeros[4].replace(",", "."))
    iva = int(float(numeros[3].replace(",", ".")))
    df = pd.DataFrame(
        {
            "data": data,
            "nr_fatura": nr_fatura,
            "produto": produto,
            "unidade": unidade,
            "preco_sem_iva": preco_sem_iva,
            "iva": iva,
            "fornecedor": "BlueSpring",
            "descricao": "Contabilidade",
        },
        index=[0],
    )
    return df


def process_pdf_kitch(text):
    nr_fatura = re.search(r"n.º (.*) O", text).groups(0)[0]
    data = pd.Timestamp(re.search(r"\d{4}-\d{2}-\d{2}", text).group())
    item = re.search(r"AT (.*)?(?= Kitch,)", text).groups(0)[0]
    produto = re.search(r".+?(?= €)", item).group()
    preco_sem_iva = float(
        re.search(r"Uni \d+ \d+% € (\d+,\d+)", item).groups(0)[0].replace(",", ".")
    )
    unidade = int(re.search(r"Uni (\d)", item).groups(0)[0])
    iva = int(re.search(r"(\d+)%", item).groups(0)[0])
    df = pd.DataFrame(
        {
            "data": data,
            "nr_fatura": nr_fatura,
            "produto": produto,
            "unidade": unidade,
            "preco_sem_iva": preco_sem_iva,
            "iva": iva,
            "fornecedor": "Kitch",
            "descricao": "Servicos",
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
    preco_sem_iva = float(
        re.search(r" (.*?) ", item).group().replace(".", "").replace(",", ".")
    )
    unidade = int(re.search(r"(.*?).", item).group())
    iva = int(re.findall(r"(.*?) ", item)[3].split(".")[0])
    df = pd.DataFrame(
        {
            "data": data,
            "nr_fatura": nr_fatura,
            "produto": produto,
            "unidade": unidade,
            "preco_sem_iva": preco_sem_iva,
            "iva": iva,
            "fornecedor": "Weat",
            "descricao": "Renda",
        },
        index=[0],
    )
    return df


def process_pdf_makro(text):
    iva_dict = {"2": 23, "4": 6, "5": 13}
    data = re.search(r"Data da venda (\d{2}-\d{2}-\d{4})", text).groups(0)[0]
    nr_fatura = re.search(r"Factura Nº (\w+ \d+\/\d+)", text).groups(0)[0]
    text = text.split("MOT")[1]
    items = re.findall(
        r"(?<= )\d{5,14}.*? [\d,]+ [\d,]+ [\d,]+ [\d,]+ [\d,]+ \d",
        text,
    )
    df = pd.DataFrame()
    for item in items:
        numbers = (
            re.search(r"[\d,]+ [\d,]+ [\d,]+ [\d,]+ [\d,]+ \d", item).group().split(" ")
        )
        codigo = re.search(r"\d{5,14}", item).group()
        produto = re.search(
            r"\d{5,14} (.*) \w{2} [\d,]+ [\d,]+ [\d,]+ [\d,]+ [\d,]+ \d", item
        ).groups(0)[0]
        peso = int(float(numbers[1].replace(",", ".")))
        unidade = int(numbers[3])
        preco_sem_iva = float(numbers[4].replace(",", "."))
        iva = iva_dict[numbers[5]]
        row = {
            "codigo": codigo,
            "produto": produto,
            "peso": peso,
            "unidade": unidade,
            "preco_sem_iva": preco_sem_iva,
            "iva": iva,
        }
        df = pd.concat(
            [df, pd.DataFrame.from_records(row, index=[0])], ignore_index=True
        )
    df = (
        df.groupby(["codigo", "produto", "peso", "iva"])[["unidade", "preco_sem_iva"]]
        .sum()
        .reset_index()
    )
    df = df.assign(
        data=pd.Timestamp(data),
        nr_fatura=nr_fatura,
        fornecedor="Makro",
    )
    return df


def process_pdf_triponto(text):
    data = pd.Timestamp(re.search(r"Data: (\d{2}\/\d{2}\/\d{4})", text).groups(0)[0])
    nr_fatura = re.search(r"Fatura (\w+ \d+\/\d+)", text).groups(0)[0]
    items = re.findall(r"\d{4,5} [\d,]+ [\d,]+ [\d,]+ [\d,]+ [\d,]+ .*?unidades", text)
    df = pd.DataFrame()
    for item in items:
        caixas = int(re.search(r"(\d+) ?unidade", item).groups(0)[0])
        codigo = item.split(" ")[0]
        unidade = int(float(item.split(" ")[1].replace(",", "."))) * caixas
        preco_sem_iva = float(item.split(" ")[4].replace(",", "."))
        iva = int(item.split(" ")[5])
        produto = (" ").join(item.split(" ")[6:])
        row = {
            "codigo": codigo,
            "produto": produto,
            "unidade": unidade,
            "preco_sem_iva": preco_sem_iva,
            "iva": iva,
        }
        df = pd.concat(
            [df, pd.DataFrame.from_records(row, index=[0])], ignore_index=True
        )
    df = df.assign(
        data=data, nr_fatura=nr_fatura, fornecedor="Triponto", descricao="Packaging"
    )
    return df


def upload_faturas_from_files():
    stored_df = 1
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
            text = re.sub(" +", " ", text)
            st.write(text)
            if "Quinta Encantada Unip. Lda" in text:
                df = pd.concat([df, process_pdf_rota(text)])
            elif "Blue Spring II - Soluções Empresariais, Lda" in text:
                df = pd.concat([df, process_pdf_bluespring(text)])
            elif "Kitch, Unipessoal Lda" in text:
                df = pd.concat([df, process_pdf_kitch(text)])
            elif "WGH, LDA" in text:
                df = pd.concat([df, process_pdf_weat(text)])
            elif "MAKRO CASH & CARRY PORTUGAL, S.A." in text:
                df = pd.concat([df, process_pdf_makro(text)])
            elif "Triponto, Serviços Comerciais, Lda." in text:
                df = pd.concat([df, process_pdf_triponto(text)])
            else:
                st.error("Fornecedor não reconhecido")
                st.stop()
        df = pd.concat([stored_df, stored_df, df]).drop_duplicates(
            subset=["data", "nr_fatura", "produto"], keep=False
        )
        if not df.empty:
            df.to_sql("yasai_faturas", engine, if_exists="append", index=False)
            st.experimental_memo.clear()
            st.success("Faturas guardadas")
        else:
            st.experimental_memo.clear()
            st.info("Sem faturas novas")


def upload_faturas_manually():
    stored_df = 1
    cols = st.columns(5)
    linhas = cols[0].number_input("Linhas", 1, step=1)
    data = cols[1].date_input("Data", value=datetime.date.today())
    nr_fatura = cols[2].text_input("Número de Fatura")
    fornecedores = stored_df.fornecedor.sort_values().unique().tolist()
    fornecedores.insert(0, "Novo")
    produtos = stored_df.produto.sort_values().unique().tolist()
    produtos.insert(0, "Novo")
    descricoes = stored_df.descricao.sort_values().unique().tolist()
    descricoes.insert(0, "Novo")
    fornecedor = cols[3].selectbox("Fornecedor", fornecedores)
    if fornecedor == "Novo":
        fornecedor = cols[4].text_input("Novo fornecedor")
    if not fornecedor or not nr_fatura:
        st.warning("Dados Incompletos")
        st.stop()
    df = pd.DataFrame()
    for i in range(int(linhas)):
        cols = st.columns([0.5, 1, 1, 0.5, 0.5, 0.5, 0.5, 0.5])
        codigo = cols[0].text_input("Codigo", key=f"codigo_{i}")
        produto = cols[1].selectbox("Produto", produtos, key=f"produto_{i}")
        if produto == "Novo":
            produto = cols[1].text_input("Novo produto", key=f"novo_produto_{i}")
        descricao = cols[2].selectbox("Descrição", descricoes, key=f"descricao_{i}")
        if descricao == "Novo":
            descricao = cols[2].text_input("Nova descrição", key=f"nova_descricao_{i}")
        peso = cols[3].number_input("Peso (kg)", min_value=0.0, key=f"peso_{i}")
        unidade = cols[4].number_input("Unidade", min_value=0, key=f"unidade_{i}")
        preco_sem_iva = cols[5].number_input(
            "Preco Sem IVA", min_value=0.0, key=f"preco_sem_iva_{i}"
        )
        preco_com_iva = cols[6].number_input(
            "Preco Com IVA", min_value=0.0, key=f"preco_com_iva_{i}"
        )
        iva = cols[7].selectbox("IVA", options=[0, 6, 23], key=f"iva_{i}")
        if preco_sem_iva and preco_com_iva:
            st.warning("Não pode ter os dois preços")
            st.stop()
        if preco_com_iva and iva:
            preco_sem_iva = preco_com_iva / (1 + iva / 100)
        if not unidade or not descricao or not produto:
            st.warning("Linha incompleta")
            st.stop()
        df = pd.concat(
            [
                df,
                pd.DataFrame.from_records(
                    {
                        "codigo": codigo,
                        "produto": produto,
                        "descricao": descricao,
                        "peso": peso,
                        "unidade": unidade,
                        "preco_sem_iva": round(preco_sem_iva, 2),
                        "iva": iva,
                    },
                    index=[0],
                ),
            ]
        )
    df = df.assign(data=pd.Timestamp(data), fornecedor=fornecedor, nr_fatura=nr_fatura)
    st.write(df.reset_index(drop=True))
    st.write(
        "Total Sem Iva:",
        df.preco_sem_iva.sum(),
        "IVA:",
        (df.preco_sem_iva * df.iva / 100).sum(),
        "TOTAL:",
        df.preco_sem_iva.sum() + (df.preco_sem_iva * df.iva / 100).sum(),
    )
    confirmar = st.button("Confirmar?")
    if confirmar:
        st.experimental_memo.clear()
        stored_df = 1
        df = pd.concat([stored_df, stored_df, df]).drop_duplicates(keep=False)
        if not df.empty:
            df.to_sql("yasai_faturas", engine, if_exists="append", index=False)
            st.experimental_memo.clear()
            st.success("Fatura guardada")
        else:
            st.info("Sem faturas novas")


def upload_uber_to_supabase(df, table):
    stored_df = pd.read_sql(
        f"SELECT * FROM {table}",
        engine,
        index_col="id",
        parse_dates="Time Customer Ordered",
    )
    df = pd.concat([stored_df, stored_df, df]).drop_duplicates(keep=False)
    if not df.empty:
        df.to_sql(table, engine, index=False, if_exists="append")


def upload_uber():
    files = st.file_uploader("Upload CSV", ["csv"], True, key="upload_uber")
    for file in files:
        df = pd.read_csv(file)
        if "Menu Item Count" in df.columns:
            df = df[
                [
                    "Order ID",
                    "Menu Item Count",
                    "Ticket Size",
                    "Time Customer Ordered",
                    "Original Prep Time",
                ]
            ]
            df["Time Customer Ordered"] = df["Time Customer Ordered"].apply(
                pd.Timestamp
            )
            upload_uber_to_supabase(df, "uber_order_history")
        elif "Rating Type" in df.columns:
            df = df.loc[df["Rating Type"] == "customer_to_restaurant"]
            df = df[["Order ID", "Rating Tags", "Comment"]]
            upload_uber_to_supabase(df, "uber_customer_feedback")
        elif "Item Name" in df.columns:
            df = df[
                [
                    "Order ID",
                    "Item Name",
                    "Item Price",
                    "Rating Value",
                    "Rating Tags",
                    "Comment",
                ]
            ]
            df = df.dropna(subset="Item Name")
            upload_uber_to_supabase(df, "uber_item_feedback")
        elif "Payout" in df.columns:
            df = df[
                [
                    "Order ID",
                    "Food Sales (excl VAT)",
                    "VAT2 on Food Sales",
                    "Discount on Food (incl VAT)",
                    "Delivery Fee (incl VAT)",
                    "Uber Service Fee after Discount (ex VAT)",
                    "VAT on Uber Service Fees after Discount",
                    "Gratuity",
                ]
            ]
            df["Order ID"] = df["Order ID"].str[1:]
            df = df.dropna(subset="Order ID")
            upload_uber_to_supabase(df, "uber_payment_details")


def uber():
    tab1, tab2 = st.tabs(["Ver Dados", "Carregar Ficheiros"])
    with tab1:
        df1 = pd.read_sql("SELECT * FROM uber_payment_details", engine, index_col="id")
        df2 = pd.read_sql("SELECT * FROM uber_item_feedback", engine, index_col="id")
        df3 = pd.read_sql(
            "SELECT * FROM uber_customer_feedback", engine, index_col="id"
        )
        df4 = pd.read_sql("SELECT * FROM uber_order_history", engine, index_col="id")
        data_frames = [df1, df2, df3, df4]
        df_merged = reduce(
            lambda left, right: pd.merge(left, right, on=["Order ID"], how="outer"),
            data_frames,
        )
        st.write(df_merged)
    with tab2:
        upload_uber()


def faturas():
    tab1, tab2, tab3 = st.tabs(
        ["Ver Dados", "Carregar Ficheiros", "Introduzir Manualmente"]
    )
    with tab1:
        st.write("ok")
    with tab2:
        upload_faturas_from_files()
    with tab3:
        upload_faturas_manually()


def upload_santander():
    files = st.file_uploader("Upload CSV", ["csv"], True, key="upload_santander")
    for file in files:
        df = pd.read_csv(file, delimiter=";", header=None, encoding="latin")
        df = df[[1, 3, 5, 6, 7]]
        df.columns = ["data", "descricao", "debito", "credito", "saldo"]
        df[["debito", "credito", "saldo"]] = (
            df[["debito", "credito", "saldo"]]
            .apply(lambda x: x.str[1:])
            .apply(lambda x: x.str.replace(",", "."))
            .apply(lambda x: x.str.replace(" ", float))
        ).astype(float)
        df.data = pd.to_datetime(df.data, dayfirst=True)
        stored_df = pd.read_sql(
            "SELECT * FROM yasai_santander", engine, index_col="id", parse_dates="data"
        )
        df = pd.concat([stored_df, stored_df, df]).drop_duplicates(keep=False)
        if not df.empty:
            df.to_sql("yasai_santander", engine, if_exists="append", index=False)


def santander():
    tab1, tab2 = st.tabs(["Ver Dados", "Carregar Ficheiros"])
    with tab1:
        df = pd.read_sql(
            "SELECT * FROM yasai_santander", engine, index_col="id", parse_dates="data"
        )
        st.write(
            df.groupby(pd.Grouper(key="data", freq="W")).agg(
                {"credito": "sum", "debito": "sum"}
            )
        )

    with tab2:
        upload_santander()


if "yasai" not in st.session_state:
    login()
    st.stop()

option = st.sidebar.radio("", ["Uber", "Faturas", "Santander"])
if option == "Uber":
    uber()
elif option == "Faturas":
    faturas()
elif option == "Santander":
    santander()
