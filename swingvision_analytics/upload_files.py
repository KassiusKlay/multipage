"""
Upload Files module for SwingVision analytics
Contains functions for file upload, validation, and data processing
"""

import hashlib
import re
import uuid

import pandas as pd
import streamlit as st
from db import engine

from .data_processing import (
    STATUS_COMPLETED,
    STATUS_LABELS,
    STATUS_OTHER,
    STATUS_RETIRED,
    STATUS_TIME,
    STATUS_UNFINISHED,
    infer_match_status,
    format_scoreline,
    scoreline_from_sets,
)
from .schema import ensure_schema


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


def normalize_sets(df):
    return df.rename(
        columns={
            "Set": "set",
            "Host Score": "host_score",
            "Guest Score": "guest_score",
            "Host Tiebreak Score": "host_tiebreak_score",
            "Guest Tiebreak Score": "guest_tiebreak_score",
            "Set Winner": "set_winner",
            "Super Tiebreak": "super_tiebreak",
            "Start Time": "start_time",
            "Video Time": "video_time",
            "Duration": "duration",
        }
    )


def _parse_bool(value):
    if pd.isna(value):
        return None
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"true", "1", "yes"}


def extract_match_metadata(settings_df, filename=None):
    try:
        start_time_raw = settings_df.loc[0, "Start Time"]
        location_raw = settings_df.loc[0, "Location"]
        host_raw = settings_df.loc[0, "Host Team"]
        guest_raw = settings_df.loc[0, "Guest Team"]

        start_time = pd.to_datetime(start_time_raw)
        end_time = None
        if "End Time" in settings_df.columns and pd.notna(settings_df.loc[0, "End Time"]):
            # End Time is often time-only; keep as string time if date missing
            try:
                end_time = pd.to_datetime(settings_df.loc[0, "End Time"])
            except Exception:
                end_time = None

        location = str(location_raw).strip() if pd.notna(location_raw) else ""
        host = str(host_raw).strip() if pd.notna(host_raw) else ""
        guest = str(guest_raw).strip() if pd.notna(guest_raw) else ""

        ad_scoring = (
            _parse_bool(settings_df.loc[0, "Ad Scoring"])
            if "Ad Scoring" in settings_df.columns
            else None
        )
        match_tiebreak = (
            _parse_bool(settings_df.loc[0, "Match Tiebreak"])
            if "Match Tiebreak" in settings_df.columns
            else None
        )
        games_per_set = (
            int(settings_df.loc[0, "Games per Set"])
            if "Games per Set" in settings_df.columns
            and pd.notna(settings_df.loc[0, "Games per Set"])
            else None
        )
        sets_per_match = (
            int(settings_df.loc[0, "Sets per Match"])
            if "Sets per Match" in settings_df.columns
            and pd.notna(settings_df.loc[0, "Sets per Match"])
            else None
        )

        match_date = None
        if filename:
            match = re.search(r"(\d{4}-\d{2}-\d{2})", filename)
            if match:
                match_date = pd.to_datetime(match.group(1)).date()

        timestamp_str = str(int(start_time.timestamp()))
        data_string = f"ST:{timestamp_str}|LOC:{location}|HOST:{host}|GUEST:{guest}"
        hash_bytes = hashlib.md5(data_string.encode("utf-8")).digest()
        match_id = uuid.UUID(bytes=hash_bytes)

        return {
            "match_id": match_id,
            "start_time": start_time,
            "end_time": end_time,
            "location": location,
            "host": host,
            "guest": guest,
            "match_date": match_date,
            "ad_scoring": ad_scoring,
            "match_tiebreak": match_tiebreak,
            "games_per_set": games_per_set,
            "sets_per_match": sets_per_match,
        }

    except Exception as e:
        print(f"Error extracting metadata: {e}")
        import traceback

        traceback.print_exc()
        return None


def validate_shots_export(shots_df, host, guest):
    """
    Detect bugged dual-perspective / duplicated SwingVision shot exports.
    Returns (ok: bool, messages: list[str], severity: 'ok'|'warn'|'error').
    """
    messages = []
    if shots_df.empty:
        return False, ["Shots sheet is empty."], "error"

    players = shots_df["player"].value_counts()
    host_count = int(players.get(host, 0))
    guest_count = int(players.get(guest, 0))
    total = len(shots_df)

    # Exact duplicate rows
    exact_dupes = int(shots_df.duplicated().sum())
    if exact_dupes > 0:
        messages.append(f"{exact_dupes} exact duplicate shot rows.")

    # Dual-perspective: same point+shot+video_time, different players
    dual = 0
    if {"point", "shot", "video_time", "player"}.issubset(shots_df.columns):
        grouped = shots_df.groupby(["point", "shot", "video_time"])["player"].nunique()
        dual = int((grouped > 1).sum())
        if dual > 0:
            messages.append(
                f"{dual} dual-perspective events (same timestamp, both players labeled)."
            )

    # Heavily skewed player counts suggest mirrored rows
    if host_count and guest_count:
        ratio = max(host_count, guest_count) / max(min(host_count, guest_count), 1)
        if ratio >= 1.8 and dual > 10:
            messages.append(
                f"Player row imbalance {host_count}:{guest_count} (ratio {ratio:.1f}×)."
            )

    if exact_dupes > 50 or dual > 30 or (
        host_count and guest_count and max(host_count, guest_count) / total > 0.65 and dual > 10
    ):
        messages.append(
            "This export looks bugged (like a dual-perspective re-export). "
            "Reprocess the video in SwingVision and upload again."
        )
        return False, messages, "error"

    if exact_dupes or dual:
        return True, messages, "warn"

    messages.append(
        f"Shots look clean ({total} rows, {host_count} host / {guest_count} guest)."
    )
    return True, messages, "ok"


def checksum_against_stats(points_df, stats_df, host_is_host=True):
    """Compare a few derived point totals to the Stats sheet. Returns list of notes."""
    notes = []
    if stats_df is None or stats_df.empty or "Stat Name" not in stats_df.columns:
        return notes

    stats = stats_df.set_index("Stat Name")

    def _stat_sum(name, role="Host"):
        cols = [c for c in stats.columns if str(c).startswith(role)]
        if name not in stats.index:
            return None
        vals = pd.to_numeric(stats.loc[name, cols], errors="coerce")
        return float(vals.fillna(0).sum())

    host_points_won = int((points_df["point_winner"] == "host").sum())
    guest_points_won = int((points_df["point_winner"] == "guest").sum())
    stats_host = _stat_sum("Total Points Won", "Host")
    stats_guest = _stat_sum("Total Points Won", "Guest")

    if stats_host is not None and abs(stats_host - host_points_won) > 1:
        notes.append(
            f"Checksum: Points sheet host won {host_points_won}, Stats says {int(stats_host)}."
        )
    if stats_guest is not None and abs(stats_guest - guest_points_won) > 1:
        notes.append(
            f"Checksum: Points sheet guest won {guest_points_won}, Stats says {int(stats_guest)}."
        )

    if not notes:
        notes.append("Checksum: Points totals match Stats sheet.")
    return notes


def upload_files():
    ensure_schema()
    existing_ids = get_stored_match_ids()
    # Normalize UUID comparison (DB may return UUID or str)
    existing_ids = {str(x) for x in existing_ids}

    uploaded_files = st.file_uploader(
        "Upload SwingVision Excel files", type="xlsx", accept_multiple_files=True
    )

    if not uploaded_files:
        return

    progress_bar = st.progress(0)
    for i, file in enumerate(uploaded_files):
        progress_bar.progress((i + 1) / len(uploaded_files))

        xls = pd.ExcelFile(file)
        required = {"Settings", "Points", "Shots"}
        missing = required - set(xls.sheet_names)
        if missing:
            st.error(f"{file.name}: missing sheets {sorted(missing)}")
            continue

        settings = xls.parse("Settings")
        meta = extract_match_metadata(settings, file.name)
        if meta is None:
            st.error(f"Failed to extract metadata from {file.name}")
            continue

        match_id = meta["match_id"]
        if st.checkbox("Show debug info", key=f"debug_{i}"):
            st.write(meta)
            st.write(f"**Already exists:** {str(match_id) in existing_ids}")

        if str(match_id) in existing_ids:
            st.info(f"Match already uploaded: {file.name}")
            continue

        points_df = normalize_points(xls.parse("Points"))
        shots_df = normalize_shots(xls.parse("Shots"))

        ok, messages, severity = validate_shots_export(
            shots_df, meta["host"], meta["guest"]
        )
        for msg in messages:
            if severity == "error":
                st.error(f"{file.name}: {msg}")
            elif severity == "warn":
                st.warning(f"{file.name}: {msg}")
            else:
                st.caption(f"{file.name}: {msg}")

        force = False
        if severity == "error":
            force = st.checkbox(
                f"Force upload anyway: {file.name}",
                key=f"force_{i}",
                value=False,
            )
            if not force:
                st.warning(
                    f"Skipped upload of {file.name} due to export quality issues."
                )
                continue

        stats_notes = []
        if "Stats" in xls.sheet_names:
            stats_notes = checksum_against_stats(points_df, xls.parse("Stats"))
            for note in stats_notes:
                st.caption(f"{file.name}: {note}")

        sets_df = None
        if "Sets" in xls.sheet_names:
            sets_df = normalize_sets(xls.parse("Sets"))
            sets_df["match_id"] = match_id
            if "super_tiebreak" in sets_df.columns:
                sets_df["super_tiebreak"] = sets_df["super_tiebreak"].map(_parse_bool)

        auto_status = infer_match_status(
            match_id,
            sets_df if sets_df is not None else pd.DataFrame(),
            meta.get("sets_per_match", 3),
        )
        raw_score = scoreline_from_sets(
            match_id, sets_df if sets_df is not None else pd.DataFrame()
        )

        match_status = STATUS_COMPLETED
        if auto_status != STATUS_COMPLETED:
            st.warning(
                f"{file.name}: incomplete match detected — "
                f"{format_scoreline(raw_score, auto_status)}"
            )
            reason = st.selectbox(
                f"Why was this match incomplete? ({file.name})",
                options=[
                    STATUS_TIME,
                    STATUS_RETIRED,
                    STATUS_UNFINISHED,
                    STATUS_OTHER,
                ],
                format_func=lambda s: {
                    STATUS_TIME: "Ran out of time",
                    STATUS_RETIRED: "Injury / retirement",
                    STATUS_UNFINISHED: "Unfinished (other / unknown)",
                    STATUS_OTHER: "Other",
                }[s],
                key=f"status_{i}",
            )
            st.caption(
                "Points and shots will still be analyzed; this match won't count "
                "as a win or loss."
            )
            if not st.button(
                f"Confirm & upload incomplete match: {file.name}",
                key=f"confirm_incomplete_{i}",
            ):
                st.info("Select a reason, then confirm to upload.")
                continue
            match_status = reason
        else:
            st.caption(
                f"{file.name}: completed — {raw_score or 'score from Sets sheet'}"
            )

        points_df["match_id"] = match_id
        shots_df["match_id"] = match_id

        match_row = pd.DataFrame(
            [
                {
                    "match_id": match_id,
                    "start_time": meta["start_time"],
                    "end_time": meta["end_time"],
                    "location": meta["location"],
                    "host_team": meta["host"],
                    "guest_team": meta["guest"],
                    "match_date": meta["match_date"],
                    "ad_scoring": meta["ad_scoring"],
                    "match_tiebreak": meta["match_tiebreak"],
                    "games_per_set": meta["games_per_set"],
                    "sets_per_match": meta["sets_per_match"],
                    "match_status": match_status,
                }
            ]
        )

        match_row.to_sql(
            "swingvision_matches", engine, if_exists="append", index=False
        )
        points_df.to_sql("swingvision_points", engine, if_exists="append", index=False)
        shots_df.to_sql("swingvision_shots", engine, if_exists="append", index=False)
        if sets_df is not None and not sets_df.empty:
            sets_df.to_sql(
                "swingvision_sets", engine, if_exists="append", index=False
            )

        existing_ids.add(str(match_id))
        st.success(f"Uploaded match: {file.name}")

    st.cache_data.clear()


def render_upload_files_tab():
    """Render the upload files tab"""
    st.title("📤 Upload SwingVision Files")
    st.markdown(
        """
Uploads **Settings** (incl. format flags), **Points**, **Shots**, and **Sets**.
Exports with duplicated / dual-perspective shot rows are rejected with a warning
so they don't skew stroke analysis.

Incomplete matches (time / injury / abandoned) are kept for coaching stats but
excluded from win/loss.
"""
    )
    upload_files()
