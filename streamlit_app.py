import streamlit as st
import bcrypt

# Initialize session state
if "logged_in" not in st.session_state:
    st.session_state.logged_in = False


def check_credentials():
    """Check if provided credentials are valid against stored secrets."""
    if (
        not st.session_state.username
        or not st.session_state.password
        or st.session_state.username != st.secrets["app"]["user"]
        or not bcrypt.checkpw(
            st.session_state.password.encode(), st.secrets["app"]["password"].encode()
        )
    ):
        st.warning("Tente novamente")
        return False
    else:
        st.session_state.logged_in = True
        st.rerun()
        return True


def login():
    """Display the login form."""
    st.header("Login Required")
    st.write("Please log in to access restricted applications.")

    with st.form("login_form"):
        st.text_input("Username", key="username")
        st.text_input("Password", key="password", type="password")
        submitted = st.form_submit_button("Login")

        if submitted:
            check_credentials()


def logout():
    """Log out the user."""
    st.session_state.logged_in = False
    st.session_state.username = ""
    st.session_state.password = ""
    st.rerun()


# Define all pages
nutrition = st.Page("nutrition.py", title="Nutrition", icon=":material/restaurant:")
remnote = st.Page("remnote.py", title="Remnote", icon=":material/note_add:")
swingvision = st.Page(
    "swingvision.py", title="Swingvision", icon=":material/sports_tennis:"
)

sispat = st.Page("sispat.py", title="Sispat", icon=":material/health_and_safety:")
invoice = st.Page("invoice.py", title="Invoice", icon=":material/receipt:")
budget = st.Page("budget.py", title="Budget", icon=":material/wallet:")

stock_drop = st.Page("stock_drop.py", title="Stock Drop", icon=":material/inventory:")
degiro = st.Page("degiro.py", title="Degiro", icon=":material/account_balance_wallet:")

# Free pages (always available)
free_pages = [nutrition, remnote, swingvision]

# Restricted pages (only available when logged in)
restricted_pages = [sispat, invoice, budget]

# Deprecated pages (always available)
deprecated_pages = [stock_drop, degiro]

# Set page config
st.set_page_config(
    page_title="Dashboard", page_icon=":material/dashboard:", layout="wide"
)

# Always show full navigation structure
page_dict = {"Free": free_pages}
page_dict["Deprecated"] = deprecated_pages

# Add restricted section conditionally
if st.session_state.logged_in:
    logout_page = st.Page(logout, title="Log out", icon=":material/logout:")
    page_dict["Account"] = [logout_page]
    page_dict["Restricted"] = restricted_pages
else:
    # Show login page in Restricted section when not logged in
    page_dict["Restricted"] = [
        st.Page(login, title="Login Required", icon=":material/login:")
    ]

# Always show the full navigation
pg = st.navigation(page_dict)

pg.run()
