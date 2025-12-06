"""
Raw Data module for SwingVision analytics
Contains functions for displaying raw data tables
"""

import streamlit as st


def render_raw_data_tab(matches, points, shots):
    """Render the raw data tab"""
    st.header("📋 Raw Data")

    data_type = st.selectbox("Select data type:", ["Matches", "Points", "Shots"])

    if data_type == "Matches":
        st.dataframe(matches, width='stretch')
    elif data_type == "Points":
        st.dataframe(points, width='stretch')
    else:
        st.dataframe(shots, width='stretch')
