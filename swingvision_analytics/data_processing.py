"""
Data Processing module for SwingVision analytics
Contains functions for data retrieval and processing
"""

import streamlit as st
import pandas as pd
from db import engine

HOST = "Joao Cassis"


@st.cache_data
def get_stored_data():
    matches = pd.read_sql(
        "SELECT * FROM swingvision_matches", engine, parse_dates=["start_time"]
    )
    points = pd.read_sql("SELECT * FROM swingvision_points", engine)
    shots = pd.read_sql("SELECT * FROM swingvision_shots", engine)
    return matches, points, shots


@st.cache_data
def process_data(matches, points, shots):
    points = points.merge(
        matches[["match_id", "guest_team"]], on="match_id", how="left"
    )
    points["match_server"] = points.apply(
        lambda r: "Joao Cassis" if r["match_server"] == "host" else r["guest_team"],
        axis=1,
    )
    points["point_winner"] = points.apply(
        lambda r: "Joao Cassis" if r["point_winner"] == "host" else r["guest_team"],
        axis=1,
    )
    points.drop(columns="guest_team", inplace=True)
    shots = shots[shots.stroke != "Feed"].copy()
    # After loading the CSVs
    points["match_id"] = points["match_id"].astype(str)
    matches["match_id"] = matches["match_id"].astype(str)
    shots["match_id"] = shots["match_id"].astype(str)

    return matches, points, shots


def calculate_match_metrics(matches, points, shots):
    """Calculate tennis metrics using detail column from points data for accuracy"""

    match_metrics = []

    for _, match in matches.iterrows():
        match_id = match["match_id"]
        match_points = points[points["match_id"] == match_id]
        match_shots = shots[shots["match_id"] == match_id]
        my_shots = match_shots[match_shots["player"] == HOST]

        # Basic match info
        metrics = {
            "match_id": match_id,
            "match_date": match["match_date"],
            "opponent": match["guest_team"],
            "location": match["location"],
        }

        # === SERVE METRICS USING DETAIL COLUMN ===
        serve_points = match_points[match_points["match_server"] == HOST]

        if len(serve_points) > 0:
            total_serve_points = len(serve_points)

            # Aces and Service Winners from detail
            my_aces = len(
                serve_points[
                    (serve_points["point_winner"] == HOST)
                    & (serve_points["detail"] == "Ace")
                ]
            )

            my_service_winners = len(
                serve_points[
                    (serve_points["point_winner"] == HOST)
                    & (serve_points["detail"] == "Service Winner")
                ]
            )

            # Double faults from detail
            my_double_faults = len(
                serve_points[
                    (serve_points["point_winner"] != HOST)
                    & (serve_points["detail"] == "Double Fault")
                ]
            )

            # Use shots data for serve percentages and speeds (more detailed)
            my_first_serves = my_shots[my_shots["type"] == "first_serve"]
            my_second_serves = my_shots[my_shots["type"] == "second_serve"]

            # First serve statistics
            first_serves_in = len(my_first_serves[my_first_serves["result"] == "In"])
            first_serve_pct = (
                first_serves_in / total_serve_points if total_serve_points > 0 else 0
            )

            # First serve points won
            first_serve_points_df = serve_points.merge(
                my_first_serves[my_first_serves["result"] == "In"][
                    ["set", "game", "point"]
                ],
                on=["set", "game", "point"],
                how="inner",
            )
            first_serve_won = len(
                first_serve_points_df[first_serve_points_df["point_winner"] == HOST]
            )
            first_serve_won_pct = (
                first_serve_won / first_serves_in if first_serves_in > 0 else 0
            )

            # Second serve statistics
            second_serves_in = len(my_second_serves[my_second_serves["result"] == "In"])
            second_serve_attempts = len(my_second_serves)
            second_serve_pct = (
                second_serves_in / second_serve_attempts
                if second_serve_attempts > 0
                else 0
            )

            # Second serve points won
            second_serve_points_df = serve_points.merge(
                my_second_serves[my_second_serves["result"] == "In"][
                    ["set", "game", "point"]
                ],
                on=["set", "game", "point"],
                how="inner",
            )
            second_serve_won = len(
                second_serve_points_df[second_serve_points_df["point_winner"] == HOST]
            )
            second_serve_won_pct = (
                second_serve_won / second_serves_in if second_serves_in > 0 else 0
            )

            # Serve speeds
            first_serve_speed = (
                my_first_serves["speed"].mean() if len(my_first_serves) > 0 else 0
            )
            second_serve_speed = (
                my_second_serves["speed"].mean() if len(my_second_serves) > 0 else 0
            )

        else:
            first_serve_pct = second_serve_pct = 0
            first_serve_won_pct = second_serve_won_pct = 0
            first_serve_speed = second_serve_speed = 0
            my_double_faults = my_aces = my_service_winners = 0

        # === RETURN METRICS ===
        return_points = match_points[match_points["match_server"] != HOST]

        if len(return_points) > 0:
            my_first_returns = my_shots[my_shots["type"] == "first_return"]
            my_second_returns = my_shots[my_shots["type"] == "second_return"]

            # First return points won
            first_return_points_df = return_points.merge(
                my_first_returns[["set", "game", "point"]],
                on=["set", "game", "point"],
                how="inner",
            )
            first_return_won = len(
                first_return_points_df[first_return_points_df["point_winner"] == HOST]
            )
            first_return_attempts = len(first_return_points_df)
            first_return_won_pct = (
                first_return_won / first_return_attempts
                if first_return_attempts > 0
                else 0
            )

            # Second return points won
            second_return_points_df = return_points.merge(
                my_second_returns[["set", "game", "point"]],
                on=["set", "game", "point"],
                how="inner",
            )
            second_return_won = len(
                second_return_points_df[second_return_points_df["point_winner"] == HOST]
            )
            second_return_attempts = len(second_return_points_df)
            second_return_won_pct = (
                second_return_won / second_return_attempts
                if second_return_attempts > 0
                else 0
            )

            # Return speeds
            first_return_speed = (
                my_first_returns["speed"].mean() if len(my_first_returns) > 0 else 0
            )
            second_return_speed = (
                my_second_returns["speed"].mean() if len(my_second_returns) > 0 else 0
            )
        else:
            first_return_won_pct = second_return_won_pct = 0
            first_return_speed = second_return_speed = 0

        # === WINNERS AND ERRORS FROM DETAIL COLUMN ===
        # My winners when I win the point
        my_winner_points = match_points[match_points["point_winner"] == HOST]

        my_forehand_winners = len(
            my_winner_points[my_winner_points["detail"] == "Forehand Winner"]
        )

        my_backhand_winners = len(
            my_winner_points[my_winner_points["detail"] == "Backhand Winner"]
        )

        # Total winners (excluding aces/service winners to avoid double counting)
        my_winners = my_forehand_winners + my_backhand_winners

        # My unforced errors when opponent wins the point
        opponent_winner_points = match_points[match_points["point_winner"] != HOST]

        my_forehand_errors = len(
            opponent_winner_points[
                opponent_winner_points["detail"] == "Forehand Unforced Error"
            ]
        )

        my_backhand_errors = len(
            opponent_winner_points[
                opponent_winner_points["detail"] == "Backhand Unforced Error"
            ]
        )

        my_unforced_errors = my_forehand_errors + my_backhand_errors

        # === OPPONENT ERRORS THAT WON ME POINTS ===
        # Points I won due to opponent errors
        opponent_forehand_errors = len(
            my_winner_points[my_winner_points["detail"] == "Forehand Unforced Error"]
        )

        opponent_backhand_errors = len(
            my_winner_points[my_winner_points["detail"] == "Backhand Unforced Error"]
        )

        opponent_double_faults = len(
            my_winner_points[my_winner_points["detail"] == "Double Fault"]
        )

        opponent_unforced_errors = (
            opponent_forehand_errors + opponent_backhand_errors + opponent_double_faults
        )

        # === BREAK POINTS ===
        break_point_opportunities = len(
            match_points[
                (match_points["match_server"] != HOST) & (match_points["break_point"])
            ]
        )
        break_points_won = len(
            match_points[
                (match_points["match_server"] != HOST)
                & (match_points["break_point"])
                & (match_points["point_winner"] == HOST)
            ]
        )
        break_points_won_pct = (
            break_points_won / break_point_opportunities
            if break_point_opportunities > 0
            else 0
        )

        break_points_against = len(
            match_points[
                (match_points["match_server"] == HOST) & (match_points["break_point"])
            ]
        )
        break_points_saved = len(
            match_points[
                (match_points["match_server"] == HOST)
                & (match_points["break_point"])
                & (match_points["point_winner"] == HOST)
            ]
        )
        break_points_saved_pct = (
            break_points_saved / break_points_against if break_points_against > 0 else 0
        )

        # === ADDITIONAL METRICS ===
        total_points = len(match_points)
        points_won = len(match_points[match_points["point_winner"] == HOST])
        points_won_pct = points_won / total_points if total_points > 0 else 0

        # Service games won
        service_games = serve_points.groupby(["set", "game"]).last()
        service_games_won = len(service_games[service_games["point_winner"] == HOST])
        service_games_total = len(service_games)
        service_games_won_pct = (
            service_games_won / service_games_total if service_games_total > 0 else 0
        )

        # Return games won
        return_games = return_points.groupby(["set", "game"]).last()
        return_games_won = len(return_games[return_games["point_winner"] == HOST])
        return_games_total = len(return_games)
        return_games_won_pct = (
            return_games_won / return_games_total if return_games_total > 0 else 0
        )

        # === WINNER/ERROR RATIOS ===
        winner_error_ratio = (
            my_winners / my_unforced_errors
            if my_unforced_errors > 0
            else float("inf") if my_winners > 0 else 0
        )
        forehand_winner_error_ratio = (
            my_forehand_winners / my_forehand_errors
            if my_forehand_errors > 0
            else float("inf") if my_forehand_winners > 0 else 0
        )
        backhand_winner_error_ratio = (
            my_backhand_winners / my_backhand_errors
            if my_backhand_errors > 0
            else float("inf") if my_backhand_winners > 0 else 0
        )

        # Add all metrics to the dictionary
        metrics.update(
            {
                "total_points": total_points,
                "points_won": points_won,
                "points_won_pct": points_won_pct,
                # Serve metrics
                "first_serve_pct": first_serve_pct,
                "first_serve_won_pct": first_serve_won_pct,
                "first_serve_speed": first_serve_speed,
                "second_serve_pct": second_serve_pct,
                "second_serve_won_pct": second_serve_won_pct,
                "second_serve_speed": second_serve_speed,
                "double_faults": my_double_faults,
                "aces": my_aces,
                "service_winners": my_service_winners,
                "service_games_won_pct": service_games_won_pct,
                # Return metrics
                "first_return_won_pct": first_return_won_pct,
                "first_return_speed": first_return_speed,
                "second_return_won_pct": second_return_won_pct,
                "second_return_speed": second_return_speed,
                "return_games_won_pct": return_games_won_pct,
                # Winners and errors
                "winners": my_winners,
                "forehand_winners": my_forehand_winners,
                "backhand_winners": my_backhand_winners,
                "unforced_errors": my_unforced_errors,
                "forehand_errors": my_forehand_errors,
                "backhand_errors": my_backhand_errors,
                # Opponent errors that helped me
                "opponent_unforced_errors": opponent_unforced_errors,
                "opponent_forehand_errors": opponent_forehand_errors,
                "opponent_backhand_errors": opponent_backhand_errors,
                "opponent_double_faults": opponent_double_faults,
                # Ratios
                "winner_error_ratio": winner_error_ratio,
                "forehand_winner_error_ratio": forehand_winner_error_ratio,
                "backhand_winner_error_ratio": backhand_winner_error_ratio,
                # Break points
                "break_points_won_pct": break_points_won_pct,
                "break_points_saved_pct": break_points_saved_pct,
            }
        )

        match_metrics.append(metrics)

    return pd.DataFrame(match_metrics)
