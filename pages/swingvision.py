"""
Refactored SwingVision Analytics Dashboard
Main entry point for the Streamlit application
"""

import streamlit as st
from swingvision_analytics import (
    dashboard,
    performance_evolution,
    analytics,
    raw_data,
    match_details,
    upload_files,
    data_processing,
)


def main_page():
    """Main dashboard page"""
    st.title("🎾 SwingVision Analytics Dashboard")

    # Get and process data
    matches, points, shots = data_processing.get_stored_data()

    if matches.empty:
        st.warning("No match data found. Please upload some SwingVision files first.")
        return

    matches, points, shots = data_processing.process_data(matches, points, shots)

    # Calculate match metrics
    match_metrics_df = data_processing.calculate_match_metrics(matches, points, shots)

    # Create tabs for different views
    tab1, tab2, tab3, tab4, tab5 = st.tabs(
        [
            "📊 Dashboard",
            "📈 Performance Evolution",
            "📊 Analytics",
            "📋 Raw Data",
            "🔍 Match Details",
        ]
    )

    with tab1:
        dashboard.render_dashboard_tab(matches, points, shots, match_metrics_df)

    with tab2:
        performance_evolution.render_performance_evolution_tab(
            matches, points, shots, match_metrics_df
        )

    with tab3:
        analytics.render_analytics_tab(matches, points, shots)

    with tab4:
        raw_data.render_raw_data_tab(matches, points, shots)

    with tab5:
        match_details.render_match_details_tab(matches, points, shots, match_metrics_df)


def main():
    """Main application entry point"""
    st.set_page_config(
        page_title="SwingVision Analytics",
        page_icon="🎾",
        layout="wide",
        initial_sidebar_state="expanded",
    )

    # Navigation
    option = st.sidebar.radio(
        "Navigation", ["🏠 Dashboard", "📤 Upload Files"], label_visibility="collapsed"
    )

    if option == "🏠 Dashboard":
        main_page()
    else:
        upload_files.render_upload_files_tab()


if __name__ == "__main__":
    main()
