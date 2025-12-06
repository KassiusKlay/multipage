import streamlit as st

nutrition = st.Page("nutrition.py", title="Nutrition", icon=":material/restaurant:")
remnote = st.Page("remnote.py", title="Remnote", icon=":material/note_add:")
swingvision = st.Page("swingvision.py", title="Swingvision", icon=":material/sports_tennis:")

sispat = st.Page("sispat.py", title="Sispat", icon=":material/health_and_safety:")
invoice = st.Page("invoice.py", title="Invoice", icon=":material/receipt:")
budget = st.Page("budget.py", title="Budget", icon=":material/wallet:")

stock_drop = st.Page("stock_drop.py", title="Stock Drop", icon=":material/inventory:")
degiro = st.Page("degiro.py", title="Degiro", icon=":material/account_balance_wallet:")

pages = {"Free": [ nutrition, remnote, swingvision], "Restricted": [sispat, invoice, budget], "Deprecated": [stock_drop, degiro]}

pg = st.navigation(pages)
st.set_page_config(page_title="Dashboard", page_icon=":material/dashboard:", layout="wide")
pg.run()