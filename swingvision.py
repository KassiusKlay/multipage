"""
Refactored SwingVision Analytics Dashboard
Main entry point for the Streamlit application
"""

import streamlit as st
from swingvision_analytics import (
    dashboard,
    performance_evolution,
    shot_analysis,
    match_analysis,
    tactical_analysis,
    decision_coach,
    raw_data,
    match_details,
    upload_files,
    data_processing,
)


def main_page():
    """Main dashboard page"""
    st.title("🎾 SwingVision Analytics Dashboard")

    matches, points, shots, sets = data_processing.get_stored_data()

    if matches.empty:
        st.warning("No match data found. Please upload some SwingVision files first.")
        return

    matches, points, shots, sets = data_processing.process_data(
        matches, points, shots, sets
    )

    match_metrics_df = data_processing.calculate_match_metrics(matches, points, shots)

    tab1, tab2, tab3, tab4, tab5, tab6, tab7, tab8 = st.tabs(
        [
            "🧭 Decision Coach",
            "📊 Dashboard",
            "📈 Performance Evolution",
            "🎾 Shot Analysis",
            "📊 Match Analysis",
            "🧠 Tactical Analysis",
            "📋 Raw Data",
            "🔍 Match Details",
        ]
    )

    with tab1:
        decision_coach.render_decision_coach_tab(matches, points, shots, sets)

    with tab2:
        dashboard.render_dashboard_tab(matches, points, shots, match_metrics_df)

    with tab3:
        performance_evolution.render_performance_evolution_tab(
            matches, points, shots, match_metrics_df
        )

    with tab4:
        shot_analysis.render_shot_analysis_tab(matches, points, shots)

    with tab5:
        match_analysis.render_match_analysis_tab(matches, points, shots)

    with tab6:
        tactical_analysis.render_tactical_analysis_tab(matches, points, shots)

    with tab7:
        raw_data.render_raw_data_tab(matches, points, shots, sets)

    with tab8:
        match_details.render_match_details_tab(matches, points, shots, match_metrics_df)


def main():
    """Main application entry point"""

    option = st.sidebar.radio(
        "Navigation", ["🏠 Dashboard", "📤 Upload Files"], label_visibility="collapsed"
    )

    if option == "🏠 Dashboard":
        main_page()
    else:
        upload_files.render_upload_files_tab()


if __name__ == "__main__":
    main()
