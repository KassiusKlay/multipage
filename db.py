from sqlalchemy import create_engine
import streamlit as st


@st.cache_resource  # ✅ Ensures engine is cached in Streamlit
def get_engine():
    return create_engine(
        f"postgresql://"
        f'{st.secrets["postgres"]["user"]}:'
        f'{st.secrets["postgres"]["password"]}@'
        f'{st.secrets["postgres"]["host"]}:'
        f'{st.secrets["postgres"]["port"]}/'
        f'{st.secrets["postgres"]["dbname"]}',
        pool_size=10,  # ✅ Keep 10 connections open
        max_overflow=20,  # ✅ Allow up to 20 extra
        pool_pre_ping=True,  # ✅ Prevents stale connections
        pool_recycle=1800,  # ✅ Reuses connections every 30 minutes
    )


engine = get_engine()
