"""
Data Processing module for SwingVision analytics
Contains functions for data retrieval and processing
"""

import streamlit as st
import pandas as pd
from db import engine
from sqlalchemy import text

HOST = "Joao Cassis"

STATUS_COMPLETED = "completed"
STATUS_UNFINISHED = "unfinished"
STATUS_TIME = "time"
STATUS_RETIRED = "retired"
STATUS_OTHER = "other"

INCOMPLETE_STATUSES = {
    STATUS_UNFINISHED,
    STATUS_TIME,
    STATUS_RETIRED,
    STATUS_OTHER,
}

STATUS_LABELS = {
    STATUS_COMPLETED: "completed",
    STATUS_UNFINISHED: "unfinished",
    STATUS_TIME: "stopped early",
    STATUS_RETIRED: "retired",
    STATUS_OTHER: "incomplete",
}


def _table_exists(table_name: str) -> bool:
    with engine.connect() as conn:
        result = conn.execute(
            text(
                """
                SELECT EXISTS (
                    SELECT 1 FROM information_schema.tables
                    WHERE table_schema = 'public' AND table_name = :t
                )
                """
            ),
            {"t": table_name},
        )
        return bool(result.scalar())


@st.cache_data
def get_stored_data():
    matches = pd.read_sql(
        "SELECT * FROM swingvision_matches", engine, parse_dates=["start_time"]
    )
    points = pd.read_sql("SELECT * FROM swingvision_points", engine)
    shots = pd.read_sql("SELECT * FROM swingvision_shots", engine)
    if _table_exists("swingvision_sets"):
        sets = pd.read_sql("SELECT * FROM swingvision_sets", engine)
    else:
        sets = pd.DataFrame()
    return matches, points, shots, sets


def sets_needed_to_win(sets_per_match) -> int:
    try:
        spm = int(sets_per_match) if sets_per_match is not None else 3
    except (TypeError, ValueError):
        spm = 3
    return spm // 2 + 1


def infer_match_status(match_id, sets: pd.DataFrame, sets_per_match=3) -> str:
    """
    Auto-detect completed vs unfinished from the Sets sheet.
    SwingVision marks abandoned sets/games with set_winner='draw'.
    """
    if sets is None or sets.empty or "match_id" not in sets.columns:
        return STATUS_COMPLETED  # no sets data — assume completed legacy

    match_sets = sets[sets["match_id"].astype(str) == str(match_id)]
    if match_sets.empty or "set_winner" not in match_sets.columns:
        return STATUS_COMPLETED

    winners = match_sets["set_winner"].astype(str).str.lower().str.strip()
    if (winners == "draw").any():
        return STATUS_UNFINISHED

    host_sets = int((winners == "host").sum())
    guest_sets = int((winners == "guest").sum())
    need = sets_needed_to_win(sets_per_match)
    if max(host_sets, guest_sets) >= need:
        return STATUS_COMPLETED
    # Sets exist but nobody reached the required set count
    return STATUS_UNFINISHED


def is_completed_status(status) -> bool:
    if status is None or (isinstance(status, float) and pd.isna(status)):
        return True
    return str(status) == STATUS_COMPLETED


def match_won_from_sets(match_id, sets: pd.DataFrame):
    """Return True/False/None from official Sets sheet winners."""
    if sets is None or sets.empty or "match_id" not in sets.columns:
        return None
    match_sets = sets[sets["match_id"].astype(str) == str(match_id)]
    if match_sets.empty or "set_winner" not in match_sets.columns:
        return None
    winners = match_sets["set_winner"].astype(str).str.lower().str.strip()
    if (winners == "draw").any():
        return None
    host_sets = (winners == "host").sum()
    guest_sets = (winners == "guest").sum()
    need_unknown = host_sets == guest_sets
    if need_unknown:
        return None
    return bool(host_sets > guest_sets)


def scoreline_from_sets(match_id, sets: pd.DataFrame) -> str:
    if sets is None or sets.empty:
        return ""
    match_sets = sets[sets["match_id"].astype(str) == str(match_id)].sort_values("set")
    if match_sets.empty:
        return ""
    parts = []
    for _, row in match_sets.iterrows():
        hs, gs = int(row["host_score"]), int(row["guest_score"])
        part = f"{hs}-{gs}"
        htb = row.get("host_tiebreak_score", 0) or 0
        gtb = row.get("guest_tiebreak_score", 0) or 0
        try:
            htb, gtb = int(htb), int(gtb)
        except Exception:
            htb = gtb = 0
        if htb or gtb:
            part += f" ({htb}-{gtb})"
        parts.append(part)
    return ", ".join(parts)


def format_scoreline(scoreline: str, status: str) -> str:
    base = scoreline or ""
    if is_completed_status(status):
        return base
    label = STATUS_LABELS.get(str(status), str(status))
    if base:
        return f"{base} ({label})"
    return f"({label})"


@st.cache_data
def process_data(matches, points, shots, sets=None):
    if sets is None:
        sets = pd.DataFrame()

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

    # Explicit blank Detail handling
    points["detail"] = points["detail"].fillna("").astype(str).str.strip()
    points["detail_blank"] = points["detail"] == ""

    # Boolean-ish flags from SwingVision strings
    for col in ("break_point", "set_point", "favorited"):
        if col in points.columns:
            points[col] = (
                points[col]
                .astype(str)
                .str.lower()
                .isin(["true", "1", "yes"])
            )

    # Drop practice feeds; keep Type==none only when it's a real stroke later filtered in sequences
    shots = shots[shots.stroke != "Feed"].copy()

    points["match_id"] = points["match_id"].astype(str)
    matches["match_id"] = matches["match_id"].astype(str)
    shots["match_id"] = shots["match_id"].astype(str)
    if not sets.empty and "match_id" in sets.columns:
        sets = sets.copy()
        sets["match_id"] = sets["match_id"].astype(str)

    # Attach official result, completion status, scoreline
    match_won = []
    scorelines = []
    statuses = []
    for _, match in matches.iterrows():
        mid = match["match_id"]
        sets_per = match.get("sets_per_match", 3)
        stored_status = match.get("match_status")
        if (
            stored_status is None
            or (isinstance(stored_status, float) and pd.isna(stored_status))
            or str(stored_status).strip() == ""
        ):
            status = infer_match_status(mid, sets, sets_per)
        else:
            status = str(stored_status).strip()

        won = match_won_from_sets(mid, sets)
        if not is_completed_status(status):
            won = None

        raw_score = scoreline_from_sets(mid, sets)
        match_won.append(won)
        statuses.append(status)
        scorelines.append(format_scoreline(raw_score, status))

    matches = matches.copy()
    matches["match_status"] = statuses
    matches["match_won_official"] = match_won
    matches["scoreline"] = scorelines
    matches["is_completed"] = matches["match_status"].map(is_completed_status)

    return matches, points, shots, sets


def resolve_match_won(match_row, points_won_pct=None):
    """
    Prefer Sets sheet for completed matches.
    Never invent a W/L for unfinished / retired / time-stopped matches.
    """
    status = match_row.get("match_status")
    if not is_completed_status(status):
        return None

    official = match_row.get("match_won_official")
    if official is True or official is False:
        return bool(official)

    # Completed (or legacy) without sets winners — fall back to points
    if points_won_pct is not None:
        return points_won_pct > 0.5
    return None


def completed_matches(df: pd.DataFrame) -> pd.DataFrame:
    """Filter to matches that finished with a real result."""
    if df is None or df.empty:
        return df
    if "is_completed" in df.columns:
        return df[df["is_completed"]].copy()
    if "match_status" in df.columns:
        return df[df["match_status"].map(is_completed_status)].copy()
    if "match_won" in df.columns:
        return df[df["match_won"].notna()].copy()
    return df


def calculate_match_metrics(matches, points, shots):
    """Calculate tennis metrics using detail column from points data for accuracy"""

    match_metrics = []

    for _, match in matches.iterrows():
        match_id = match["match_id"]
        match_points = points[points["match_id"] == match_id]
        match_shots = shots[shots["match_id"] == match_id]
        my_shots = match_shots[match_shots["player"] == HOST]

        metrics = {
            "match_id": match_id,
            "match_date": match["match_date"],
            "opponent": match["guest_team"],
            "location": match["location"],
            "scoreline": match.get("scoreline", ""),
            "match_status": match.get("match_status", STATUS_COMPLETED),
            "is_completed": bool(match.get("is_completed", True)),
        }

        # === SERVE METRICS USING DETAIL COLUMN ===
        serve_points = match_points[match_points["match_server"] == HOST]

        if len(serve_points) > 0:
            total_serve_points = len(serve_points)

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

            my_double_faults = len(
                serve_points[
                    (serve_points["point_winner"] != HOST)
                    & (serve_points["detail"] == "Double Fault")
                ]
            )

            my_first_serves = my_shots[my_shots["type"] == "first_serve"]
            my_second_serves = my_shots[my_shots["type"] == "second_serve"]

            first_serves_in = len(my_first_serves[my_first_serves["result"] == "In"])
            first_serve_pct = (
                first_serves_in / total_serve_points if total_serve_points > 0 else 0
            )

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

            second_serves_in = len(my_second_serves[my_second_serves["result"] == "In"])
            second_serve_attempts = len(my_second_serves)
            second_serve_pct = (
                second_serves_in / second_serve_attempts
                if second_serve_attempts > 0
                else 0
            )

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
        my_winner_points = match_points[match_points["point_winner"] == HOST]

        my_forehand_winners = len(
            my_winner_points[my_winner_points["detail"] == "Forehand Winner"]
        )
        my_backhand_winners = len(
            my_winner_points[my_winner_points["detail"] == "Backhand Winner"]
        )
        my_winners = my_forehand_winners + my_backhand_winners

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

        blank_detail_lost = len(
            opponent_winner_points[opponent_winner_points["detail_blank"]]
        )
        blank_detail_won = len(my_winner_points[my_winner_points["detail_blank"]])
        blank_detail_total = int(match_points["detail_blank"].sum())

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

        total_points = len(match_points)
        points_won = len(match_points[match_points["point_winner"] == HOST])
        points_won_pct = points_won / total_points if total_points > 0 else 0
        match_won = resolve_match_won(match, points_won_pct)

        service_games = serve_points.groupby(["set", "game"]).last()
        service_games_won = len(service_games[service_games["point_winner"] == HOST])
        service_games_total = len(service_games)
        service_games_won_pct = (
            service_games_won / service_games_total if service_games_total > 0 else 0
        )

        return_games = return_points.groupby(["set", "game"]).last()
        return_games_won = len(return_games[return_games["point_winner"] == HOST])
        return_games_total = len(return_games)
        return_games_won_pct = (
            return_games_won / return_games_total if return_games_total > 0 else 0
        )

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

        metrics.update(
            {
                "total_points": total_points,
                "points_won": points_won,
                "points_won_pct": points_won_pct,
                "match_won": match_won,
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
                "first_return_won_pct": first_return_won_pct,
                "first_return_speed": first_return_speed,
                "second_return_won_pct": second_return_won_pct,
                "second_return_speed": second_return_speed,
                "return_games_won_pct": return_games_won_pct,
                "winners": my_winners,
                "forehand_winners": my_forehand_winners,
                "backhand_winners": my_backhand_winners,
                "unforced_errors": my_unforced_errors,
                "forehand_errors": my_forehand_errors,
                "backhand_errors": my_backhand_errors,
                "blank_detail_total": blank_detail_total,
                "blank_detail_lost": blank_detail_lost,
                "blank_detail_won": blank_detail_won,
                "opponent_unforced_errors": opponent_unforced_errors,
                "opponent_forehand_errors": opponent_forehand_errors,
                "opponent_backhand_errors": opponent_backhand_errors,
                "opponent_double_faults": opponent_double_faults,
                "winner_error_ratio": winner_error_ratio,
                "forehand_winner_error_ratio": forehand_winner_error_ratio,
                "backhand_winner_error_ratio": backhand_winner_error_ratio,
                "break_points_won_pct": break_points_won_pct,
                "break_points_saved_pct": break_points_saved_pct,
            }
        )

        match_metrics.append(metrics)

    return pd.DataFrame(match_metrics)
