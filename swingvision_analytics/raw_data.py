"""
Raw Data module for SwingVision analytics
Contains functions for displaying raw data tables
"""

import streamlit as st


def render_raw_data_tab(matches, points, shots, sets=None):
    """Render the raw data tab"""
    st.header("📋 Raw Data")

    options = ["Matches", "Points", "Shots"]
    if sets is not None and not sets.empty:
        options.append("Sets")

    data_type = st.selectbox("Select data type:", options)

    if data_type == "Matches":
        st.dataframe(matches, width="stretch")
    elif data_type == "Points":
        st.dataframe(points, width="stretch")
    elif data_type == "Sets":
        st.dataframe(sets, width="stretch")
    else:
        st.dataframe(shots, width="stretch")
