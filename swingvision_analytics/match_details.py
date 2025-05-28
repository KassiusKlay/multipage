"""
Match Details module for SwingVision analytics
Contains functions for detailed match analysis
"""

import streamlit as st


def render_match_details_tab(matches, points, shots, match_metrics_df):
    """Render the match details tab"""
    st.header("🔍 Match Details")

    if not matches.empty:
        # Match selector
        match_options = matches.apply(
            lambda x: f"{x['match_date']} vs {x['guest_team']} ({x['location']})",
            axis=1,
        ).tolist()

        selected_match_idx = st.selectbox(
            "Select a match for detailed analysis:",
            range(len(match_options)),
            format_func=lambda x: match_options[x],
        )

        selected_match_id = matches.iloc[selected_match_idx]["match_id"]

        # Show detailed match analysis
        match_points = points[points["match_id"] == selected_match_id]

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Match Statistics")
            match_stats = match_metrics_df[
                match_metrics_df["match_id"] == selected_match_id
            ]
            if not match_stats.empty:
                stats_to_show = [
                    "points_won_pct",
                    "first_serve_pct",
                    "first_serve_won_pct",
                    "winners",
                    "unforced_errors",
                    "aces",
                    "double_faults",
                ]
                for stat in stats_to_show:
                    if stat in match_stats.columns:
                        value = match_stats[stat].iloc[0]
                        if "pct" in stat:
                            st.metric(stat.replace("_", " ").title(), f"{value:.1%}")
                        else:
                            st.metric(stat.replace("_", " ").title(), f"{value:.0f}")

        with col2:
            st.subheader("Point-by-Point Details")
            if not match_points.empty:
                # Show last 10 points of the match
                recent_points = match_points.tail(10)[
                    [
                        "set",
                        "game",
                        "point",
                        "match_server",
                        "point_winner",
                        "detail",
                    ]
                ]
                st.dataframe(recent_points, use_container_width=True)
