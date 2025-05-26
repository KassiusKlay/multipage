import streamlit as st
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots
import uuid
from db import engine

HOST = "Joao Cassis"


@st.cache_data
def get_stored_match_ids():
    return pd.read_sql("SELECT match_id FROM swingvision_matches", engine)[
        "match_id"
    ].tolist()


def normalize_points(df):
    return df.rename(
        columns={
            "Point": "point",
            "Game": "game",
            "Set": "set",
            "Serve State": "serve_state",
            "Match Server": "match_server",
            "Host Game Score": "host_game_score",
            "Guest Game Score": "guest_game_score",
            "Point Winner": "point_winner",
            "Detail": "detail",
            "Break Point": "break_point",
            "Set Point": "set_point",
            "Favorited": "favorited",
            "Start Time": "start_time",
            "Video Time": "video_time",
            "Duration": "duration",
        }
    )


def normalize_shots(df):
    return df.rename(
        columns={
            "Player": "player",
            "Shot": "shot",
            "Type": "type",
            "Stroke": "stroke",
            "Spin": "spin",
            "Speed (KM/H)": "speed",
            "Point": "point",
            "Game": "game",
            "Set": "set",
            "Bounce Depth": "bounce_depth",
            "Bounce Zone": "bounce_zone",
            "Bounce Side": "bounce_side",
            "Bounce (x)": "bounce_x",
            "Bounce (y)": "bounce_y",
            "Hit Depth": "hit_depth",
            "Hit Zone": "hit_zone",
            "Hit Side": "hit_side",
            "Hit (x)": "hit_x",
            "Hit (y)": "hit_y",
            "Hit (z)": "hit_z",
            "Direction": "direction",
            "Result": "result",
            "Favorited": "favorited",
            "Start Time": "start_time",
            "Video Time": "video_time",
        }
    )


def extract_match_metadata(settings_df, filename=None):
    try:
        start_time = pd.to_datetime(settings_df.loc[0, "Start Time"])
        location = settings_df.loc[0, "Location"]
        host = settings_df.loc[0, "Host Team"]
        guest = settings_df.loc[0, "Guest Team"]
        match_date = None
        if filename:
            import re

            date_pattern = r"(\d{4}-\d{2}-\d{2})"
            match = re.search(date_pattern, filename)
            if match:
                match_date = pd.to_datetime(match.group(1)).date()
    except Exception:
        return None
    match_id = uuid.uuid5(uuid.NAMESPACE_DNS, f"{start_time}-{location}-{host}-{guest}")
    return match_id, start_time, location, host, guest, match_date


def upload_files():
    existing_ids = get_stored_match_ids()
    uploaded_files = st.file_uploader(
        "Upload SwingVision Excel files", type="xlsx", accept_multiple_files=True
    )

    if uploaded_files:
        progress_bar = st.progress(0)
        for i, file in enumerate(uploaded_files):
            progress_bar.progress((i + 1) / len(uploaded_files))

            xls = pd.ExcelFile(file)
            settings = xls.parse("Settings")
            result = extract_match_metadata(settings, file.name)
            if result is None:
                st.error(f"Failed to extract metadata from {file.name}")
                continue

            match_id, start_time, location, host, guest, match_date = result

            if match_id in existing_ids:
                st.info(f"Match already uploaded: {file.name}")
                continue

            points_df = normalize_points(xls.parse("Points"))
            shots_df = normalize_shots(xls.parse("Shots"))

            points_df["match_id"] = match_id
            shots_df["match_id"] = match_id

            match_row = pd.DataFrame(
                [
                    {
                        "match_id": match_id,
                        "start_time": start_time,
                        "location": location,
                        "host_team": host,
                        "guest_team": guest,
                        "match_date": match_date,
                    }
                ]
            )

            match_row.to_sql(
                "swingvision_matches",
                engine,
                if_exists="append",
                index=False,
            )

            points_df.to_sql(
                "swingvision_points",
                engine,
                if_exists="append",
                index=False,
            )

            shots_df.to_sql(
                "swingvision_shots",
                engine,
                if_exists="append",
                index=False,
            )
            st.success(f"Uploaded match: {file.name}")
        st.cache_data.clear()


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
    shots = shots[shots.stroke != "Feed"]
    return matches, points, shots


@st.cache_data
def get_bad_shots(shots):
    my_shots = shots[(shots["player"] == HOST)]
    total_by_stroke = my_shots.groupby("stroke").size().rename("total")
    last_shots = my_shots.loc[
        my_shots.groupby(["match_id", "set", "game", "point"])["shot"].idxmax()
    ]
    your_errors = last_shots[last_shots["result"].isin(["Out", "Net"])]
    error_by_stroke = your_errors.groupby("stroke").size().rename("error_count")
    forced_winner = []
    for _, grp in shots.groupby(["match_id", "set", "game", "point"]):
        last = grp.sort_values("shot").iloc[-1]
        if (last["player"] != HOST) and (last["result"] == "In"):
            penult = grp[grp["player"] == HOST].sort_values("shot").iloc[-1:]
            if not penult.empty:
                forced_winner.append(penult.iloc[0]["stroke"])
    opp_win_by_stroke = pd.Series(forced_winner).value_counts().rename("opp_win_count")
    bad_shots = pd.concat(
        [total_by_stroke, error_by_stroke, opp_win_by_stroke], axis=1
    ).fillna(0)
    bad_shots["error_pct"] = bad_shots["error_count"] / bad_shots["total"]
    bad_shots["opp_win_pct"] = bad_shots["opp_win_count"] / bad_shots["total"]
    bad_shots["total_pct"] = bad_shots["error_pct"] + bad_shots["opp_win_pct"]
    bad_shots = bad_shots.sort_values("total_pct", ascending=False)
    return bad_shots


@st.cache_data
def get_good_shots(shots):
    my_shots = shots[(shots["player"] == HOST)]
    total_by_stroke = my_shots.groupby("stroke").size().rename("total")
    last_shots = my_shots.loc[
        my_shots.groupby(["match_id", "set", "game", "point"])["shot"].idxmax()
    ]
    winners = last_shots[last_shots["result"] == "In"]
    winner_by_stroke = winners.groupby("stroke").size().rename("win_count")
    forced = []
    for key, group in shots.groupby(["match_id", "set", "game", "point"]):
        if group.iloc[-1]["player"] != HOST and group.iloc[-1]["result"] != "In":
            penult = group.iloc[:-1].loc[group.iloc[:-1]["player"] == HOST]
            if not penult.empty:
                forced.append(penult.iloc[-1]["stroke"])
    error_by_stroke = pd.Series(forced).value_counts().rename("opp_error_count")
    good_shots = pd.concat(
        [total_by_stroke, winner_by_stroke, error_by_stroke], axis=1
    ).fillna(0)
    good_shots["win_pct"] = good_shots["win_count"] / good_shots["total"]
    good_shots["error_pct"] = good_shots["opp_error_count"] / good_shots["total"]
    good_shots["total_pct"] = good_shots["win_pct"] + good_shots["error_pct"]
    good_shots = good_shots.sort_values("total_pct", ascending=False)
    return good_shots


@st.cache_data
def get_first_point_winner_outcome(points):
    first_points = (
        points.groupby(["match_id", "set", "game"], as_index=False)
        .first()
        .rename(columns={"point_winner": "first_point_winner"})
    )
    first_points["first_point_winner"] = first_points["first_point_winner"].apply(
        lambda x: HOST if x == HOST else "Opponent"
    )
    game_winners = (
        points.groupby(["match_id", "set", "game"], as_index=False)
        .last()
        .rename(columns={"point_winner": "game_winner"})
    )
    df = first_points.merge(game_winners, on=["match_id", "set", "game"])
    first_point_winner_outcome = (
        df.groupby("first_point_winner")
        .agg(
            games_played=("game_winner", "size"),
            games_won=("game_winner", lambda s: (s == HOST).sum()),
        )
        .assign(win_pct=lambda d: d["games_won"] / d["games_played"])
    )
    return first_point_winner_outcome


@st.cache_data
def analyze_error_factors(shots):
    my_errs = shots[
        (shots["player"] == HOST)
        & (shots["stroke"].isin(["Forehand", "Backhand"]))
        & (shots["result"].isin(["Out", "Net"]))
    ]

    rows = []
    for (_, s, g, p), group in shots.groupby(["match_id", "set", "game", "point"]):
        err = my_errs[
            (my_errs["match_id"] == _)
            & (my_errs["set"] == s)
            & (my_errs["game"] == g)
            & (my_errs["point"] == p)
        ]
        if err.empty:
            continue
        err_idx = err["shot"].iloc[0]
        prior = group[group["shot"] == err_idx - 1]
        if prior.empty or prior["player"].iloc[0] == HOST:
            continue
        prev = prior.iloc[0]
        e = err.iloc[0]
        rows.append(
            {
                "match_id": _,
                "set": s,
                "game": g,
                "point": p,
                "error_stroke": e["stroke"],
                "error_result": e["result"],
                "prev_stroke": prev["stroke"],
                "prev_spin": prev["spin"],
                "prev_speed": prev["speed"],
                "prev_bounce_depth": prev["bounce_depth"],
                "prev_bounce_x": prev["bounce_x"],
                "prev_bounce_y": prev["bounce_y"],
                "error_hit_zone": e["hit_zone"],
                "error_hit_x": e["hit_x"],
                "error_hit_y": e["hit_y"],
                "error_hit_direction": e["direction"],
            }
        )
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    error_summary = df.groupby("error_stroke").agg(
        count=("prev_speed", "size"),
        avg_prev_speed=("prev_speed", "mean"),
        most_problematic_spin=(
            "prev_spin",
            lambda x: x.value_counts().index[0] if len(x) > 0 else None,
        ),
        most_problematic_spin_pct=(
            "prev_spin",
            lambda x: x.value_counts().iloc[0] / len(x) if len(x) > 0 else 0,
        ),
        deep_pct=("prev_bounce_depth", lambda x: (x == "deep").mean()),
        down_the_line=("error_hit_direction", lambda x: (x == "down the line").mean()),
    )
    return error_summary


@st.cache_data
def analyze_success_factors(shots):
    my_successes = shots[
        (shots["player"] == HOST)
        & (shots["stroke"].isin(["Forehand", "Backhand"]))
        & (shots["result"] == "In")
    ]

    rows = []
    for (_, s, g, p), group in shots.groupby(["match_id", "set", "game", "point"]):
        success = my_successes[
            (my_successes["match_id"] == _)
            & (my_successes["set"] == s)
            & (my_successes["game"] == g)
            & (my_successes["point"] == p)
        ]
        if success.empty:
            continue

        for _, succ in success.iterrows():
            prior = group[group["shot"] == succ["shot"] - 1]
            if prior.empty or prior["player"].iloc[0] == HOST:
                continue
            prev = prior.iloc[0]
            rows.append(
                {
                    "match_id": _,
                    "set": s,
                    "game": g,
                    "point": p,
                    "success_stroke": succ["stroke"],
                    "prev_stroke": prev["stroke"],
                    "prev_spin": prev["spin"],
                    "prev_speed": prev["speed"],
                    "prev_bounce_depth": prev["bounce_depth"],
                    "prev_bounce_x": prev["bounce_x"],
                    "prev_bounce_y": prev["bounce_y"],
                    "success_hit_zone": succ["hit_zone"],
                    "success_hit_x": succ["hit_x"],
                    "success_hit_y": succ["hit_y"],
                    "success_hit_direction": succ["direction"],
                }
            )

    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame()

    success_summary = df.groupby("success_stroke").agg(
        count=("prev_speed", "size"),
        avg_prev_speed=("prev_speed", "mean"),
        most_helpful_spin=(
            "prev_spin",
            lambda x: x.value_counts().index[0] if len(x) > 0 else None,
        ),
        most_helpful_spin_pct=(
            "prev_spin",
            lambda x: x.value_counts().iloc[0] / len(x) if len(x) > 0 else 0,
        ),
        deep_pct=("prev_bounce_depth", lambda x: (x == "deep").mean()),
        down_the_line=(
            "success_hit_direction",
            lambda x: (x == "down the line").mean(),
        ),
    )
    return success_summary


@st.cache_data
def compare_error_vs_success_factors(shots):
    """Compare characteristics of opponent shots that lead to errors vs successes"""
    error_summary = analyze_error_factors(shots)
    success_summary = analyze_success_factors(shots)

    if error_summary.empty or success_summary.empty:
        return pd.DataFrame()

    comparison = pd.DataFrame()

    for stroke in ["Forehand", "Backhand"]:
        if stroke in error_summary.index and stroke in success_summary.index:
            comparison = pd.concat(
                [
                    comparison,
                    pd.DataFrame(
                        {
                            "stroke": [stroke],
                            "error_count": [error_summary.loc[stroke, "count"]],
                            "success_count": [success_summary.loc[stroke, "count"]],
                            "error_avg_prev_speed": [
                                error_summary.loc[stroke, "avg_prev_speed"]
                            ],
                            "success_avg_prev_speed": [
                                success_summary.loc[stroke, "avg_prev_speed"]
                            ],
                            "error_problematic_spin": [
                                error_summary.loc[stroke, "most_problematic_spin"]
                            ],
                            "error_problematic_spin_pct": [
                                error_summary.loc[stroke, "most_problematic_spin_pct"]
                            ],
                            "success_helpful_spin": [
                                success_summary.loc[stroke, "most_helpful_spin"]
                            ],
                            "success_helpful_spin_pct": [
                                success_summary.loc[stroke, "most_helpful_spin_pct"]
                            ],
                            "error_deep_pct": [error_summary.loc[stroke, "deep_pct"]],
                            "success_deep_pct": [
                                success_summary.loc[stroke, "deep_pct"]
                            ],
                        }
                    ),
                ]
            )
    return comparison


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


@st.cache_data
def create_evolution_chart(match_metrics_df, selected_metrics):
    """Create evolution chart for selected metrics"""

    if match_metrics_df.empty or not selected_metrics:
        return go.Figure()

    # Sort by date
    df_sorted = match_metrics_df.sort_values("match_date")

    fig = go.Figure()

    # Add a trace for each selected metric
    for metric in selected_metrics:
        if metric in df_sorted.columns:
            fig.add_trace(
                go.Scatter(
                    x=df_sorted["match_date"],
                    y=df_sorted[metric],
                    mode="lines+markers",
                    name=metric.replace("_", " ").title(),
                    hovertemplate=f'<b>{metric.replace("_", " ").title()}</b><br>'
                    + "Date: %{x}<br>"
                    + "Value: %{y:.2f}<br>"
                    + "<extra></extra>",
                )
            )

    fig.update_layout(
        title="Tennis Performance Evolution Over Time",
        xaxis_title="Match Date",
        yaxis_title="Value",
        hovermode="x unified",
        height=500,
    )

    return fig


@st.cache_data
def create_performance_dashboard(match_metrics_df):
    """Create a comprehensive performance dashboard"""
    if match_metrics_df.empty:
        return go.Figure()

    # Calculate averages
    avg_metrics = match_metrics_df.select_dtypes(include=["float64", "int64"]).mean()

    # Create subplots
    fig = make_subplots(
        rows=2,
        cols=2,
        subplot_titles=(
            "Serve Performance",
            "Return Performance",
            "Winners vs Errors",
            "Break Point Performance",
        ),
        specs=[
            [{"secondary_y": True}, {"secondary_y": True}],
            [{"secondary_y": False}, {"secondary_y": False}],
        ],
    )

    # Serve Performance
    fig.add_trace(
        go.Bar(
            name="First Serve %",
            x=["Current"],
            y=[avg_metrics.get("first_serve_pct", 0) * 100],
            marker_color="lightblue",
            showlegend=False,
        ),
        row=1,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            name="Second Serve %",
            x=["Current"],
            y=[avg_metrics.get("second_serve_pct", 0) * 100],
            marker_color="darkblue",
            showlegend=False,
        ),
        row=1,
        col=1,
    )

    # Return Performance
    fig.add_trace(
        go.Bar(
            name="1st Return Won %",
            x=["Current"],
            y=[avg_metrics.get("first_return_won_pct", 0) * 100],
            marker_color="lightgreen",
            showlegend=False,
        ),
        row=1,
        col=2,
    )
    fig.add_trace(
        go.Bar(
            name="2nd Return Won %",
            x=["Current"],
            y=[avg_metrics.get("second_return_won_pct", 0) * 100],
            marker_color="darkgreen",
            showlegend=False,
        ),
        row=1,
        col=2,
    )

    # Winners vs Errors
    fig.add_trace(
        go.Bar(
            name="Winners",
            x=["Forehand", "Backhand"],
            y=[
                avg_metrics.get("forehand_winners", 0),
                avg_metrics.get("backhand_winners", 0),
            ],
            marker_color="gold",
            showlegend=False,
        ),
        row=2,
        col=1,
    )
    fig.add_trace(
        go.Bar(
            name="Errors",
            x=["Forehand", "Backhand"],
            y=[
                avg_metrics.get("forehand_errors", 0),
                avg_metrics.get("backhand_errors", 0),
            ],
            marker_color="red",
            showlegend=False,
        ),
        row=2,
        col=1,
    )

    # Break Points
    fig.add_trace(
        go.Bar(
            name="BP Conversion",
            x=["Break Points Won", "Break Points Saved"],
            y=[
                avg_metrics.get("break_points_won_pct", 0) * 100,
                avg_metrics.get("break_points_saved_pct", 0) * 100,
            ],
            marker_color=["orange", "purple"],
            showlegend=False,
        ),
        row=2,
        col=2,
    )

    fig.update_layout(height=600, title_text="Performance Dashboard")
    return fig


@st.cache_data
def create_match_comparison_chart(match_metrics_df):
    """Create a chart comparing performance across different opponents"""
    if match_metrics_df.empty:
        return go.Figure()

    # Group by opponent and calculate averages
    opponent_stats = (
        match_metrics_df.groupby("opponent")
        .agg(
            {
                "points_won_pct": "mean",
                "first_serve_pct": "mean",
                "winners": "mean",
                "unforced_errors": "mean",
                "break_points_won_pct": "mean",
            }
        )
        .reset_index()
    )

    fig = go.Figure()

    # Add traces for different metrics
    fig.add_trace(
        go.Scatter(
            x=opponent_stats["opponent"],
            y=opponent_stats["points_won_pct"] * 100,
            mode="markers+lines",
            name="Points Won %",
            marker=dict(size=12, color="blue"),
        )
    )

    fig.update_layout(
        title="Performance vs Different Opponents",
        xaxis_title="Opponent",
        yaxis_title="Points Won %",
        height=400,
    )

    return fig


@st.cache_data
def analyze_serve_first_advantage(points):
    """Analyze if serving first in the set gives advantage to win the set"""
    first_points_per_set = (
        points.groupby(["match_id", "set"], as_index=False)
        .first()
        .rename(columns={"match_server": "set_first_server"})[
            ["match_id", "set", "set_first_server"]
        ]
    )
    last_points_per_set = (
        points.groupby(["match_id", "set"], as_index=False)
        .last()
        .rename(columns={"point_winner": "set_winner"})[
            ["match_id", "set", "set_winner"]
        ]
    )
    set_results = first_points_per_set.merge(
        last_points_per_set, on=["match_id", "set"]
    )
    set_results["i_served_first"] = set_results["set_first_server"] == HOST
    set_results["i_won_set"] = set_results["set_winner"] == HOST
    serve_first_stats = (
        set_results.groupby("i_served_first")
        .agg(
            sets_played=("i_won_set", "size"),
            sets_won=("i_won_set", "sum"),
        )
        .assign(win_pct=lambda d: d["sets_won"] / d["sets_played"])
    )
    serve_first_stats.index = serve_first_stats.index.map(
        lambda x: "Joao Cassis" if x else "Opponent"
    )
    serve_first_stats = serve_first_stats.loc[["Joao Cassis", "Opponent"]]
    serve_first_stats.index.name = "served_first"
    return serve_first_stats


def create_key_metrics_cards(match_metrics_df):
    """Create key performance metric cards"""
    if match_metrics_df.empty:
        return

    # Calculate overall averages
    avg_metrics = match_metrics_df.select_dtypes(include=["float64", "int64"]).mean()

    # Create columns for metrics cards
    col1, col2, col3, col4 = st.columns(4)

    with col1:
        st.metric(
            label="Overall Win Rate",
            value=f"{avg_metrics.get('points_won_pct', 0):.1%}",
            delta=None,
        )

    with col2:
        st.metric(
            label="First Serve %",
            value=f"{avg_metrics.get('first_serve_pct', 0):.1%}",
            delta=None,
        )

    with col3:
        st.metric(
            label="Winner/Error Ratio",
            value=f"{avg_metrics.get('winner_error_ratio', 0):.2f}",
            delta=None,
        )

    with col4:
        st.metric(
            label="Break Point Conversion",
            value=f"{avg_metrics.get('break_points_won_pct', 0):.1%}",
            delta=None,
        )


@st.cache_data
def calculate_predictive_metrics(matches, points, shots):
    """Calculate predictive metrics including Net Points for each match"""

    HOST = "Joao Cassis"
    predictive_data = []

    for _, match in matches.iterrows():
        match_id = match["match_id"]
        match_points = points[points["match_id"] == match_id]
        match_shots = shots[shots["match_id"] == match_id]
        my_shots = match_shots[match_shots["player"] == HOST]

        if len(match_points) == 0:
            continue

        # Basic match outcome
        total_points = len(match_points)
        points_won = len(match_points[match_points["point_winner"] == HOST])
        points_won_pct = points_won / total_points
        match_won = points_won_pct > 0.5

        # === NET POINTS CALCULATION ===
        # Positive shots (points I create)
        my_winner_points = match_points[match_points["point_winner"] == HOST]
        my_forehand_winners = len(
            my_winner_points[my_winner_points["detail"] == "Forehand Winner"]
        )
        my_backhand_winners = len(
            my_winner_points[my_winner_points["detail"] == "Backhand Winner"]
        )
        my_winners = my_forehand_winners + my_backhand_winners

        # Opponent errors that gave me points
        opponent_unforced_errors = len(
            my_winner_points[
                my_winner_points["detail"].isin(
                    [
                        "Forehand Unforced Error",
                        "Backhand Unforced Error",
                        "Double Fault",
                    ]
                )
            ]
        )

        positive_shots = my_winners + opponent_unforced_errors

        # Negative shots (points I give away)
        opponent_winner_points = match_points[match_points["point_winner"] != HOST]
        my_unforced_errors = len(
            opponent_winner_points[
                opponent_winner_points["detail"].isin(
                    ["Forehand Unforced Error", "Backhand Unforced Error"]
                )
            ]
        )
        my_double_faults = len(
            opponent_winner_points[opponent_winner_points["detail"] == "Double Fault"]
        )

        negative_shots = my_unforced_errors + my_double_faults

        # NET POINTS = Positive - Negative
        net_points = positive_shots - negative_shots

        # === OTHER PREDICTIVE METRICS ===
        # Winner/Error Ratio
        winner_error_ratio = (
            my_winners / my_unforced_errors
            if my_unforced_errors > 0
            else (999 if my_winners > 0 else 0)
        )

        # Service Winners (including aces)
        my_aces = len(my_winner_points[my_winner_points["detail"] == "Ace"])
        my_service_winners = len(
            my_winner_points[my_winner_points["detail"] == "Service Winner"]
        )
        total_service_winners = my_aces + my_service_winners

        # Break Point Conversion
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
        break_point_conversion = (
            break_points_won / break_point_opportunities
            if break_point_opportunities > 0
            else 0
        )

        # Return Points Won
        return_points = match_points[match_points["match_server"] != HOST]
        return_points_won = len(return_points[return_points["point_winner"] == HOST])
        return_points_won_pct = (
            return_points_won / len(return_points) if len(return_points) > 0 else 0
        )

        # First Serve Percentage
        serve_points = match_points[match_points["match_server"] == HOST]
        my_first_serves = my_shots[my_shots["type"] == "first_serve"]
        first_serves_in = len(my_first_serves[my_first_serves["result"] == "In"])
        first_serve_pct = (
            first_serves_in / len(serve_points) if len(serve_points) > 0 else 0
        )

        predictive_data.append(
            {
                "match_id": match_id,
                "match_date": match["match_date"],
                "opponent": match["guest_team"],
                "location": match["location"],
                "match_won": match_won,
                "points_won_pct": points_won_pct,
                # Net Points breakdown
                "net_points": net_points,
                "positive_shots": positive_shots,
                "negative_shots": negative_shots,
                "my_winners": my_winners,
                "opponent_errors": opponent_unforced_errors,
                "my_unforced_errors": my_unforced_errors,
                "my_double_faults": my_double_faults,
                # Other predictive metrics
                "winner_error_ratio": winner_error_ratio,
                "service_winners": total_service_winners,
                "break_point_conversion": break_point_conversion,
                "return_points_won_pct": return_points_won_pct,
                "first_serve_pct": first_serve_pct,
            }
        )

    return pd.DataFrame(predictive_data)


def create_net_points_breakdown_chart(predictive_df):
    """Create a detailed Net Points breakdown chart"""

    if predictive_df.empty:
        return go.Figure()

    # Sort by date
    df_sorted = predictive_df.sort_values("match_date")

    fig = make_subplots(
        rows=2,
        cols=1,
        subplot_titles=("Net Points by Match", "Net Points Components"),
        specs=[[{"secondary_y": False}], [{"secondary_y": False}]],
        vertical_spacing=0.15,
    )

    # Top chart: Net Points line with win/loss colors
    colors = ["green" if won else "red" for won in df_sorted["match_won"]]

    fig.add_trace(
        go.Scatter(
            x=df_sorted["match_date"],
            y=df_sorted["net_points"],
            mode="markers+lines",
            name="Net Points",
            marker=dict(color=colors, size=12),
            line=dict(color="blue"),
            hovertemplate="Date: %{x}<br>Net Points: %{y}<br>Result: %{customdata}<extra></extra>",
            customdata=["WON" if won else "LOST" for won in df_sorted["match_won"]],
        ),
        row=1,
        col=1,
    )

    # Add horizontal line at 0
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=1, col=1)

    # Bottom chart: Stacked bar showing positive vs negative shots
    fig.add_trace(
        go.Bar(
            x=df_sorted["match_date"],
            y=df_sorted["positive_shots"],
            name="Positive Shots",
            marker_color="lightgreen",
            hovertemplate="Positive: %{y}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    fig.add_trace(
        go.Bar(
            x=df_sorted["match_date"],
            y=-df_sorted["negative_shots"],  # Negative for visual effect
            name="Negative Shots",
            marker_color="lightcoral",
            hovertemplate="Negative: %{y}<extra></extra>",
        ),
        row=2,
        col=1,
    )

    # Add horizontal line at 0 for bottom chart
    fig.add_hline(y=0, line_dash="dash", line_color="gray", row=2, col=1)

    fig.update_layout(
        height=700,
        title_text="Net Points Analysis - Your Shot Impact Over Time",
        showlegend=True,
    )

    fig.update_xaxes(title_text="Match Date", row=2, col=1)
    fig.update_yaxes(title_text="Net Points", row=1, col=1)
    fig.update_yaxes(title_text="Shots Count", row=2, col=1)

    return fig


def create_predictive_dashboard(predictive_df):
    """Create dashboard showing all predictive metrics"""

    if predictive_df.empty:
        return go.Figure()

    # Calculate averages for won vs lost matches
    won_matches = predictive_df[predictive_df["match_won"]]
    lost_matches = predictive_df[~predictive_df["match_won"]]

    metrics = [
        "net_points",
        "winner_error_ratio",
        "service_winners",
        "break_point_conversion",
        "return_points_won_pct",
    ]

    won_avgs = [won_matches[metric].mean() for metric in metrics]
    lost_avgs = [lost_matches[metric].mean() for metric in metrics]

    # Format metric names
    metric_names = [
        "Net Points",
        "Winner/Error Ratio",
        "Service Winners",
        "Break Point Conv.",
        "Return Points Won",
    ]

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            name="Won Matches",
            x=metric_names,
            y=won_avgs,
            marker_color="lightgreen",
            text=[f"{val:.1f}" for val in won_avgs],
            textposition="auto",
        )
    )

    fig.add_trace(
        go.Bar(
            name="Lost Matches",
            x=metric_names,
            y=lost_avgs,
            marker_color="lightcoral",
            text=[f"{val:.1f}" for val in lost_avgs],
            textposition="auto",
        )
    )

    fig.update_layout(
        title="Key Predictive Metrics: Won vs Lost Matches",
        xaxis_title="Metrics",
        yaxis_title="Average Value",
        barmode="group",
        height=500,
    )

    return fig


def create_win_probability_gauge(current_metrics):
    """Create a win probability gauge based on current metrics"""

    # Define thresholds based on analysis
    thresholds = {
        "net_points": 15,
        "winner_error_ratio": 0.4,
        "service_winners": 10,
        "break_point_conversion": 0.5,
        "return_points_won_pct": 0.5,
    }

    # Calculate how many thresholds are met
    score = 0
    for metric, threshold in thresholds.items():
        if metric in current_metrics and current_metrics[metric] >= threshold:
            score += 1

    win_probability = (score / len(thresholds)) * 100

    fig = go.Figure(
        go.Indicator(
            mode="gauge+number+delta",
            value=win_probability,
            domain={"x": [0, 1], "y": [0, 1]},
            title={"text": "Win Probability %"},
            delta={"reference": 50},
            gauge={
                "axis": {"range": [None, 100]},
                "bar": {"color": "darkblue"},
                "steps": [
                    {"range": [0, 25], "color": "lightgray"},
                    {"range": [25, 50], "color": "gray"},
                    {"range": [50, 75], "color": "lightgreen"},
                    {"range": [75, 100], "color": "green"},
                ],
                "threshold": {
                    "line": {"color": "red", "width": 4},
                    "thickness": 0.75,
                    "value": 90,
                },
            },
        )
    )

    fig.update_layout(height=400)
    return fig


def predictive_analytics_tab(matches, points, shots):
    """Main function for the Predictive Analytics tab"""

    st.header("🎯 Predictive Analytics - What Makes You Win")

    # Calculate predictive metrics
    predictive_df = calculate_predictive_metrics(matches, points, shots)

    if predictive_df.empty:
        st.warning("No data available for predictive analysis.")
        return

    # Key insights at the top
    st.subheader("🏆 Key Insights")

    won_matches = predictive_df[predictive_df["match_won"]]
    lost_matches = predictive_df[~predictive_df["match_won"]]

    col1, col2, col3, col4 = st.columns(4)

    with col1:
        avg_net_won = won_matches["net_points"].mean() if len(won_matches) > 0 else 0
        avg_net_lost = lost_matches["net_points"].mean() if len(lost_matches) > 0 else 0
        st.metric(
            "Net Points (Won vs Lost)",
            f"{avg_net_won:.1f}",
            f"{avg_net_won - avg_net_lost:.1f}",
        )

    with col2:
        avg_ratio_won = (
            won_matches["winner_error_ratio"].mean() if len(won_matches) > 0 else 0
        )
        avg_ratio_lost = (
            lost_matches["winner_error_ratio"].mean() if len(lost_matches) > 0 else 0
        )
        st.metric(
            "Winner/Error Ratio",
            f"{avg_ratio_won:.2f}",
            f"{avg_ratio_won - avg_ratio_lost:.2f}",
        )

    with col3:
        avg_service_won = (
            won_matches["service_winners"].mean() if len(won_matches) > 0 else 0
        )
        avg_service_lost = (
            lost_matches["service_winners"].mean() if len(lost_matches) > 0 else 0
        )
        st.metric(
            "Service Winners",
            f"{avg_service_won:.1f}",
            f"{avg_service_won - avg_service_lost:.1f}",
        )

    with col4:
        avg_bp_won = (
            won_matches["break_point_conversion"].mean() if len(won_matches) > 0 else 0
        )
        avg_bp_lost = (
            lost_matches["break_point_conversion"].mean()
            if len(lost_matches) > 0
            else 0
        )
        st.metric(
            "Break Point Conv.", f"{avg_bp_won:.1%}", f"{avg_bp_won - avg_bp_lost:.1%}"
        )

    # Create tabs within the predictive analytics section
    tab1, tab2, tab3, tab4 = st.tabs(
        [
            "📊 Net Points Analysis",
            "🎯 Win Probability",
            "📈 Predictive Dashboard",
            "📋 Detailed Data",
        ]
    )

    with tab1:
        st.subheader("🎯 Net Points Breakdown")

        # Explanation
        st.info(
            """
        **Net Points = (Your Winners + Opponent Errors) - (Your Errors + Double Faults)**
        
        This measures your **shot impact** - how many points you CREATE vs GIVE AWAY.
        Positive net points mean you're creating more than you're giving away!
        """
        )

        # Net Points chart
        net_points_fig = create_net_points_breakdown_chart(predictive_df)
        st.plotly_chart(net_points_fig, use_container_width=True)

        # Target thresholds
        st.subheader("🎯 Winning Thresholds")
        st.success(
            """
        **To maximize win probability, aim for:**
        - 🎯 Net Points: +15 or higher
        - 🏆 Winner/Error Ratio: 0.4 or higher  
        - 🎾 Service Winners: 10 or more
        - ⚡ Break Point Conversion: 50% or higher
        - 🔄 Return Points Won: 50% or higher
        """
        )

    with tab2:
        st.subheader("🎯 Match Win Probability Calculator")

        st.write("Enter your current match stats to see win probability:")

        col1, col2 = st.columns(2)

        with col1:
            current_winners = st.number_input(
                "Your Winners", min_value=0, value=10, step=1
            )
            current_errors = st.number_input(
                "Your Unforced Errors", min_value=1, value=15, step=1
            )
            current_opp_errors = st.number_input(
                "Opponent Errors", min_value=0, value=20, step=1
            )
            current_dfs = st.number_input(
                "Your Double Faults", min_value=0, value=3, step=1
            )

        with col2:
            current_service_winners = st.number_input(
                "Service Winners", min_value=0, value=8, step=1
            )
            current_bp_conv = (
                st.number_input(
                    "Break Point Conversion %",
                    min_value=0.0,
                    max_value=100.0,
                    value=40.0,
                    step=5.0,
                )
                / 100
            )
            current_return_won = (
                st.number_input(
                    "Return Points Won %",
                    min_value=0.0,
                    max_value=100.0,
                    value=45.0,
                    step=5.0,
                )
                / 100
            )

        # Calculate current metrics
        current_net_points = (current_winners + current_opp_errors) - (
            current_errors + current_dfs
        )
        current_ratio = current_winners / current_errors if current_errors > 0 else 0

        current_metrics = {
            "net_points": current_net_points,
            "winner_error_ratio": current_ratio,
            "service_winners": current_service_winners,
            "break_point_conversion": current_bp_conv,
            "return_points_won_pct": current_return_won,
        }

        # Show results
        col1, col2 = st.columns([1, 1])

        with col1:
            st.metric("Net Points", f"{current_net_points:+d}")
            st.metric("Winner/Error Ratio", f"{current_ratio:.2f}")

        with col2:
            win_prob_fig = create_win_probability_gauge(current_metrics)
            st.plotly_chart(win_prob_fig, use_container_width=True)

    with tab3:
        st.subheader("📈 Predictive Performance Dashboard")

        dashboard_fig = create_predictive_dashboard(predictive_df)
        st.plotly_chart(dashboard_fig, use_container_width=True)

        # Correlation analysis
        st.subheader("🔍 Metric Correlations with Winning")

        correlation_data = []
        metrics_to_analyze = [
            "net_points",
            "winner_error_ratio",
            "service_winners",
            "break_point_conversion",
            "return_points_won_pct",
        ]

        for metric in metrics_to_analyze:
            won_avg = won_matches[metric].mean() if len(won_matches) > 0 else 0
            lost_avg = lost_matches[metric].mean() if len(lost_matches) > 0 else 0
            difference = won_avg - lost_avg
            pct_diff = abs((difference / lost_avg * 100)) if lost_avg != 0 else 0

            correlation_data.append(
                {
                    "Metric": metric.replace("_", " ").title(),
                    "Won Matches Avg": won_avg,
                    "Lost Matches Avg": lost_avg,
                    "Difference": difference,
                    "Impact %": pct_diff,
                }
            )

        corr_df = pd.DataFrame(correlation_data)
        corr_df = corr_df.sort_values("Impact %", ascending=False)

        # Format the dataframe
        st.dataframe(
            corr_df.style.format(
                {
                    "Won Matches Avg": "{:.2f}",
                    "Lost Matches Avg": "{:.2f}",
                    "Difference": "{:.2f}",
                    "Impact %": "{:.1f}%",
                }
            ),
            use_container_width=True,
        )

    with tab4:
        st.subheader("📋 Detailed Predictive Data")

        # Show the full predictive dataframe
        display_df = predictive_df.copy()

        # Format columns for better display
        percentage_cols = [
            "points_won_pct",
            "break_point_conversion",
            "return_points_won_pct",
            "first_serve_pct",
        ]
        for col in percentage_cols:
            if col in display_df.columns:
                display_df[col] = display_df[col].map("{:.1%}".format)

        # Add match result column
        display_df["Result"] = display_df["match_won"].map(
            {True: "✅ WON", False: "❌ LOST"}
        )

        # Reorder columns for better presentation
        column_order = [
            "match_date",
            "opponent",
            "Result",
            "net_points",
            "positive_shots",
            "negative_shots",
            "my_winners",
            "opponent_errors",
            "my_unforced_errors",
            "my_double_faults",
            "winner_error_ratio",
            "service_winners",
            "break_point_conversion",
            "return_points_won_pct",
        ]

        display_cols = [col for col in column_order if col in display_df.columns]
        st.dataframe(display_df[display_cols], use_container_width=True)

        # Download button
        csv = display_df.to_csv(index=False)
        st.download_button(
            label="📥 Download Predictive Data as CSV",
            data=csv,
            file_name="tennis_predictive_analytics.csv",
            mime="text/csv",
        )


def main_page():
    st.title("🎾 SwingVision Analytics Dashboard")

    matches, points, shots = get_stored_data()

    if matches.empty:
        st.warning("No match data found. Please upload some SwingVision files first.")
        return

    matches, points, shots = process_data(matches, points, shots)

    # Calculate match metrics
    match_metrics_df = calculate_match_metrics(matches, points, shots)

    # Create tabs for different views
    tab1, tab2, tab3, tab4, tab5, tab6 = st.tabs(
        [
            "📊 Dashboard",
            "📈 Performance Evolution",
            "🎯 Predictive Analytics",  # NEW TAB
            "🎾 Shot Analysis",
            "📋 Raw Data",
            "🔍 Match Details",
        ]
    )

    with tab1:
        st.header("Performance Dashboard")

        # Key metrics cards
        create_key_metrics_cards(match_metrics_df)

        # Performance dashboard
        dashboard_fig = create_performance_dashboard(match_metrics_df)
        st.plotly_chart(dashboard_fig, use_container_width=True)

        # Match comparison
        comparison_fig = create_match_comparison_chart(match_metrics_df)
        st.plotly_chart(comparison_fig, use_container_width=True)

        # Recent matches summary
        st.subheader("Recent Matches")
        if not match_metrics_df.empty:
            recent_matches = match_metrics_df.sort_values(
                "match_date", ascending=False
            ).head(5)
            display_columns = [
                "match_date",
                "opponent",
                "points_won_pct",
                "winners",
                "unforced_errors",
                "aces",
            ]
            st.dataframe(
                recent_matches[display_columns].style.format(
                    {
                        "points_won_pct": "{:.1%}",
                        "winners": "{:.0f}",
                        "unforced_errors": "{:.0f}",
                        "aces": "{:.0f}",
                    }
                ),
                use_container_width=True,
            )

    with tab2:
        st.header("📈 Performance Evolution")

        # Metric selection
        available_metrics = [
            col
            for col in match_metrics_df.columns
            if col not in ["match_id", "match_date", "opponent", "location"]
        ]

        selected_metrics = st.multiselect(
            "Select metrics to display:",
            available_metrics,
            default=["first_serve_pct", "winners", "unforced_errors", "points_won_pct"],
            format_func=lambda x: x.replace("_", " ").title(),
        )

        if selected_metrics:
            evolution_fig = create_evolution_chart(match_metrics_df, selected_metrics)
            st.plotly_chart(evolution_fig, use_container_width=True)

        # Detailed metrics table
        st.subheader("Match Metrics Table")
        if not match_metrics_df.empty:
            # Format numeric columns for better display
            formatted_df = match_metrics_df.copy()
            percentage_cols = [col for col in formatted_df.columns if "pct" in col]
            for col in percentage_cols:
                formatted_df[col] = formatted_df[col].map("{:.1%}".format)

            st.dataframe(formatted_df, use_container_width=True)

    with tab3:
        # NEW PREDICTIVE ANALYTICS TAB
        predictive_analytics_tab(matches, points, shots)
    with tab4:
        st.header("🎯 Shot Analysis")

        col1, col2 = st.columns(2)

        with col1:
            st.subheader("Best Shots")
            good_shots = get_good_shots(shots)
            if not good_shots.empty:
                st.dataframe(
                    good_shots.style.format(
                        {
                            "total_pct": "{:.1%}",
                            "win_pct": "{:.1%}",
                            "error_pct": "{:.1%}",
                        }
                    )
                )

        with col2:
            st.subheader("Problematic Shots")
            bad_shots = get_bad_shots(shots)
            if not bad_shots.empty:
                st.dataframe(
                    bad_shots.style.format(
                        {
                            "total_pct": "{:.1%}",
                            "error_pct": "{:.1%}",
                            "opp_win_pct": "{:.1%}",
                            "opp_win_count": "{:.0f}",
                        }
                    )
                )

        st.subheader("Tactical Analysis")
        col1, col2 = st.columns(2)

        with col1:
            st.write("**First Point Winner Outcome**")
            first_point_stats = get_first_point_winner_outcome(points)
            if not first_point_stats.empty:
                st.dataframe(first_point_stats.style.format({"win_pct": "{:.1%}"}))

        with col2:
            st.write("**Serve First Advantage**")
            serve_first_stats = analyze_serve_first_advantage(points)
            if not serve_first_stats.empty:
                st.dataframe(serve_first_stats.style.format({"win_pct": "{:.1%}"}))

        st.subheader("Error vs Success Comparison")
        comparison_df = compare_error_vs_success_factors(shots)
        if not comparison_df.empty:
            st.dataframe(comparison_df)

    with tab5:
        st.header("📋 Raw Data")

        data_type = st.selectbox("Select data type:", ["Matches", "Points", "Shots"])

        if data_type == "Matches":
            st.dataframe(matches, use_container_width=True)
        elif data_type == "Points":
            st.dataframe(points, use_container_width=True)
        else:
            st.dataframe(shots, use_container_width=True)

    with tab6:
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
                                st.metric(
                                    stat.replace("_", " ").title(), f"{value:.1%}"
                                )
                            else:
                                st.metric(
                                    stat.replace("_", " ").title(), f"{value:.0f}"
                                )

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


option = st.sidebar.radio(
    "Navigation", ["🏠 Dashboard", "📤 Upload Files"], label_visibility="collapsed"
)

if option == "🏠 Dashboard":
    main_page()
else:
    st.title("📤 Upload SwingVision Files")
    upload_files()
