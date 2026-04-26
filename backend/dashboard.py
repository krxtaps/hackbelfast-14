import asyncio
import sqlite3

import pandas as pd
import pydeck as pdk
import streamlit as st

from services.amenities.amenity_scoring import _load_safe_sanctuaries
from services.pathfinding_service import PathfindingService
from services.safety_engine import get_street_combined_score

st.set_page_config(page_title="SafeWalk Dashboard", page_icon="🛡️", layout="wide")


@st.cache_resource
def get_pathfinding_service(cache_version: int = 2) -> PathfindingService:
    """Keeps a single pathfinding service across Streamlit reruns."""
    _ = cache_version
    return PathfindingService()


@st.cache_data
def load_streets():
    conn = sqlite3.connect("botanic.db")
    return pd.read_sql(
        "SELECT id, name, centroid_lat as lat, centroid_lng as lon FROM street ORDER BY name",
        conn,
    )


@st.cache_data
def load_sanctuaries():
    return _load_safe_sanctuaries()


@st.cache_data
def load_routable_sanctuaries(max_distance_m: float = 50.0):
    """
    Filter sanctuaries to those that can be matched to our Botanic street network.
    Prevents selecting endpoints that will always 404.
    """
    service = get_pathfinding_service(cache_version=3)
    items = []
    for s in _load_safe_sanctuaries():
        sid = s.get("sanctuary_id")
        if not sid:
            continue
        res = service._resolve_to_nearest_street_vertex(float(s.get("lat", 0.0)), float(s.get("lng", 0.0)), max_distance_m)  # noqa: SLF001
        if "error" in res:
            continue
        items.append(s)
    return items


def get_score_sync(street_id: str, time_str: str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(get_street_combined_score(street_id, time_str))


def get_path_sync(start_lat: float, start_lng: float, end_lat: float, end_lng: float):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    service = get_pathfinding_service(cache_version=3)
    return loop.run_until_complete(
        service.find_safest_path(start_lat, start_lng, end_lat, end_lng, max_snap_distance_m=50.0)
    )


def score_to_rgb(score):
    score = max(0, min(100, score))
    if score < 50:
        r = 255
        g = int(255 * (score / 50))
        b = 0
    else:
        r = int(255 * ((100 - score) / 50))
        g = 255
        b = 0
    return [r, g, b, 255]


def normalize_route_score(score: float, min_score: float, max_score: float) -> float:
    """
    Expands clustered route scores to full 0-100 display range for visual contrast.
    """
    if max_score - min_score < 1e-6:
        return 50.0
    return max(0.0, min(100.0, ((score - min_score) / (max_score - min_score)) * 100.0))


def smooth_scores(scores: list[float], blend_strength: float = 0.65) -> list[float]:
    """
    Smooths abrupt color jumps by blending each score with immediate neighbors.
    blend_strength: 0 -> no smoothing, 1 -> strongest smoothing.
    """
    if len(scores) <= 2:
        return scores
    a = max(0.0, min(1.0, blend_strength))
    smoothed: list[float] = []
    for idx, cur in enumerate(scores):
        prev_val = scores[idx - 1] if idx > 0 else cur
        next_val = scores[idx + 1] if idx < len(scores) - 1 else cur
        neighbor_avg = (prev_val + cur + next_val) / 3.0
        smoothed.append((1.0 - a) * cur + a * neighbor_avg)
    return smoothed


def draw_map(
    layers,
    center_lat: float,
    center_lng: float,
    zoom: int = 15,
    tooltip: dict | None = None,
):
    if not layers:
        st.warning("⚠️ No data available to map.")
        return
    view_state = pdk.ViewState(latitude=center_lat, longitude=center_lng, zoom=zoom, pitch=0)
    st.pydeck_chart(
        pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip=tooltip or {"text": "{name}\n{type}"},
        )
    )


def render_original_tab(streets_df: pd.DataFrame):
    col1, col2 = st.columns([1, 3])

    with col1:
        st.subheader("Controls")
        street_names = streets_df["name"].dropna().unique().tolist()
        default_idx = 0
        if "Botanic Avenue" in street_names:
            default_idx = street_names.index("Botanic Avenue")
        selected_street_name = st.selectbox(
            "Select Street",
            street_names,
            index=default_idx,
            key="original_selected_street",
        )
        selected_street_ids = streets_df[streets_df["name"] == selected_street_name]["id"].tolist()

        st.markdown(f"*(Found {len(selected_street_ids)} segments for this street)*")
        st.markdown("---")
        st.markdown("**Simulate Time of Day**")
        time_preset = st.radio(
            "Presets:",
            ["Daytime (14:00)", "Evening (21:30)", "Late Night (23:00)", "Deep Night (03:00)", "Custom"],
            key="original_time_preset",
        )
        if time_preset == "Custom":
            hour = st.slider("Hour", 0, 23, 14, key="original_hour")
            minute = st.slider("Minute", 0, 45, 0, step=15, key="original_minute")
            time_str = f"{hour:02d}:{minute:02d}"
        else:
            time_str = time_preset.split("(")[1].split(")")[0]

    with col2:
        with st.spinner(f"Analyzing {len(selected_street_ids)} street segments..."):
            all_s_items_map = {}
            all_lines = []
            total_score = 0
            all_explanations = set()
            center_lat = 0.0
            center_lng = 0.0

            for sid in selected_street_ids:
                result = get_score_sync(sid, time_str)
                total_score += result.get("score", 0)

                lat = result.get("location", {}).get("lat", 0)
                lng = result.get("location", {}).get("lng", 0)
                center_lat += lat
                center_lng += lng

                geometry = result.get("location", {}).get("geometry", {})
                seg_score = result.get("score", 0)
                seg_color = score_to_rgb(seg_score)

                if geometry.get("type") == "LineString":
                    all_lines.append({"path": geometry["coordinates"], "color": seg_color, "score": seg_score})
                elif geometry.get("type") == "MultiLineString":
                    for line in geometry["coordinates"]:
                        all_lines.append({"path": line, "color": seg_color, "score": seg_score})

                for s in result.get("sanctuaries", {}).get("items", []):
                    if s.get("lat") and s.get("lng"):
                        all_s_items_map[(s["lat"], s["lng"])] = s

                for exp in result.get("explanations", []):
                    all_explanations.add(exp)

            avg_score = int(total_score / len(selected_street_ids)) if selected_street_ids else 0
            center_lat = center_lat / len(selected_street_ids) if selected_street_ids else 54.583
            center_lng = center_lng / len(selected_street_ids) if selected_street_ids else -5.935
            s_items = list(all_s_items_map.values())

        avg_rgb = score_to_rgb(avg_score)
        color_hex = f"#{avg_rgb[0]:02x}{avg_rgb[1]:02x}{avg_rgb[2]:02x}"
        st.markdown(
            f"### Average Safety Score @ {time_str}: <span style='color:{color_hex}'>{avg_score} / 100</span>",
            unsafe_allow_html=True,
        )

        layers = []
        if all_lines:
            street_layer = pdk.Layer(
                "PathLayer",
                data=pd.DataFrame(all_lines),
                get_path="path",
                get_color="color",
                width_scale=2,
                width_min_pixels=5,
                get_width=5,
                pickable=True,
            )
            layers.append(street_layer)

        if s_items:
            points = [
                {"lon": float(s["lng"]), "lat": float(s["lat"]), "name": s.get("name"), "type": s.get("type")}
                for s in s_items
            ]
            sanctuary_layer = pdk.Layer(
                "ScatterplotLayer",
                data=pd.DataFrame(points),
                get_position="[lon, lat]",
                get_fill_color=[255, 255, 255, 255],
                get_line_color=[0, 0, 0, 255],
                get_radius=12,
                pickable=True,
                stroked=True,
                get_line_width=2,
            )
            layers.append(sanctuary_layer)

        draw_map(layers, center_lat, center_lng)

        if s_items:
            st.success(f"{len(s_items)} Safe Sanctuaries are currently OPEN across the entire street.")
        else:
            st.warning("⚠️ No Safe Sanctuaries are open on this street right now.")

        with st.expander("Detailed Score Breakdown", expanded=True):
            def sort_key(x):
                if x.startswith("---"):
                    return "0" + x
                x_lower = x.lower()
                if "crime" in x_lower or "anti-social" in x_lower:
                    return "1" + x
                if "sanctuary" in x_lower:
                    return "2" + x
                if "amenity" in x_lower:
                    return "3" + x
                if "lamp" in x_lower or "infrastructure" in x_lower or "class" in x_lower:
                    return "4" + x
                return "5" + x

            for reason in sorted(list(all_explanations), key=sort_key):
                if reason.startswith("---"):
                    st.markdown(f"**{reason.replace('-', '').strip()}**")
                elif "Sanctuary" in reason:
                    st.write(f"🟢 {reason}")
                elif "Amenity" in reason:
                    st.write(f"🔵 {reason}")
                elif "crime" in reason.lower() or "anti-social" in reason.lower() or "caution" in reason.lower():
                    st.write(f"🔴 {reason}")
                elif (
                    "lamp" in reason.lower()
                    or "infrastructure" in reason.lower()
                    or "class" in reason.lower()
                    or "context" in reason.lower()
                ):
                    st.write(f"💡 {reason}")
                else:
                    st.write(f"ℹ️ {reason}")


def render_pathfinding_tab(streets_df: pd.DataFrame):
    st.subheader("Safety-Optimized Pathfinding")
    st.caption("Pick streets or place manual pins (lat/lng), then compute safest path.")
    street_names = sorted(streets_df["name"].dropna().unique().tolist())
    sanctuaries = load_routable_sanctuaries(50.0)
    sanctuary_options = [
        {
            "label": f"{s.get('name', 'Unknown')} ({s.get('type', 'unknown')})",
            "sanctuary_id": s.get("sanctuary_id"),
            "lat": float(s.get("lat", 0.0)),
            "lng": float(s.get("lng", 0.0)),
        }
        for s in sanctuaries
        if s.get("sanctuary_id")
    ]

    controls_col, map_col = st.columns([1, 3])

    with controls_col:
        mode = st.radio(
            "Route mode",
            ["Street to street", "Manual pins", "Sanctuary to sanctuary"],
            key="path_mode",
        )

        default_start_idx = 0
        default_end_idx = 1 if len(street_names) > 1 else 0

        default_start_name = street_names[default_start_idx]
        default_end_name = street_names[default_end_idx]
        start_name = default_start_name
        end_name = default_end_name
        if mode == "Street to street":
            start_name = st.selectbox(
                "Start street", street_names, index=default_start_idx, key="path_start_name"
            )
            end_name = st.selectbox(
                "End street", street_names, index=default_end_idx, key="path_end_name"
            )

        start_rows = streets_df[streets_df["name"] == start_name]
        end_rows = streets_df[streets_df["name"] == end_name]
        start_lat_default = float(start_rows["lat"].mean())
        start_lng_default = float(start_rows["lon"].mean())
        end_lat_default = float(end_rows["lat"].mean())
        end_lng_default = float(end_rows["lon"].mean())

        lat_min = float(streets_df["lat"].min()) - 0.01
        lat_max = float(streets_df["lat"].max()) + 0.01
        lng_min = float(streets_df["lon"].min()) - 0.01
        lng_max = float(streets_df["lon"].max()) + 0.01

        if mode == "Street to street":
            start_lat, start_lng = start_lat_default, start_lng_default
            end_lat, end_lng = end_lat_default, end_lng_default
            start_pin_label = f"Start: {start_name}"
            end_pin_label = f"End: {end_name}"
            st.caption("Using street centroids as start/end pins.")
        elif mode == "Sanctuary to sanctuary":
            if len(sanctuary_options) < 2:
                st.warning("Need at least two sanctuaries to route between.")
                start_lat, start_lng = start_lat_default, start_lng_default
                end_lat, end_lng = end_lat_default, end_lng_default
                start_pin_label = "Start: fallback street centroid"
                end_pin_label = "End: fallback street centroid"
            else:
                s_labels = [s["label"] for s in sanctuary_options]
                start_idx = 0
                end_idx = 1 if len(sanctuary_options) > 1 else 0
                start_label = st.selectbox("Start sanctuary", s_labels, index=start_idx, key="path_start_sanctuary")
                end_label = st.selectbox("End sanctuary", s_labels, index=end_idx, key="path_end_sanctuary")
                start_sel = next(s for s in sanctuary_options if s["label"] == start_label)
                end_sel = next(s for s in sanctuary_options if s["label"] == end_label)
                start_lat, start_lng = start_sel["lat"], start_sel["lng"]
                end_lat, end_lng = end_sel["lat"], end_sel["lng"]
                start_pin_label = f"Start sanctuary: {start_label}"
                end_pin_label = f"End sanctuary: {end_label}"
                st.caption("Routing directly between selected sanctuary coordinates.")
        else:
            st.caption("Adjust pin coordinates visually using the map + fields below.")
            start_lat = st.number_input(
                "Start pin latitude",
                min_value=lat_min,
                max_value=lat_max,
                value=start_lat_default,
                step=0.0001,
                format="%.6f",
                key="manual_start_lat",
            )
            start_lng = st.number_input(
                "Start pin longitude",
                min_value=lng_min,
                max_value=lng_max,
                value=start_lng_default,
                step=0.0001,
                format="%.6f",
                key="manual_start_lng",
            )
            end_lat = st.number_input(
                "End pin latitude",
                min_value=lat_min,
                max_value=lat_max,
                value=end_lat_default,
                step=0.0001,
                format="%.6f",
                key="manual_end_lat",
            )
            end_lng = st.number_input(
                "End pin longitude",
                min_value=lng_min,
                max_value=lng_max,
                value=end_lng_default,
                step=0.0001,
                format="%.6f",
                key="manual_end_lng",
            )
            start_pin_label = f"Start pin: {start_lat:.5f}, {start_lng:.5f}"
            end_pin_label = f"End pin: {end_lat:.5f}, {end_lng:.5f}"

        run_route = st.button("Compute safest route", type="primary")

    with map_col:
        if "route_result" not in st.session_state:
            st.session_state["route_result"] = None
        if "route_points" not in st.session_state:
            st.session_state["route_points"] = None

        if run_route:
            with st.spinner("Computing safest route..."):
                try:
                    st.session_state["route_result"] = get_path_sync(start_lat, start_lng, end_lat, end_lng)
                except Exception as exc:
                    st.session_state["route_result"] = {"error": f"Route computation failed: {exc}"}
                st.session_state["route_points"] = {
                    "start_lat": start_lat,
                    "start_lng": start_lng,
                    "end_lat": end_lat,
                    "end_lng": end_lng,
                }

        pin_data = pd.DataFrame(
            [
                {
                    "lon": start_lng,
                    "lat": start_lat,
                    "name": start_pin_label,
                    "type": "start",
                    "color": [60, 180, 75, 230],
                },
                {
                    "lon": end_lng,
                    "lat": end_lat,
                    "name": end_pin_label,
                    "type": "end",
                    "color": [230, 25, 75, 230],
                },
            ]
        )
        layers = [
            pdk.Layer(
                "ScatterplotLayer",
                data=pin_data,
                get_position="[lon, lat]",
                get_fill_color="color",
                get_radius=20,
                pickable=True,
            )
        ]

        route_result = st.session_state["route_result"]
        snap = route_result.get("snap", {}) if isinstance(route_result, dict) else {}
        snapped_start = route_result.get("snapped_start") if isinstance(route_result, dict) else None
        snapped_end = route_result.get("snapped_end") if isinstance(route_result, dict) else None
        if snapped_start and snapped_end:
            # Visualize snapping so it's obvious when a route doesn't truly start/end at the pins.
            snap_points = pd.DataFrame(
                [
                    {
                        "lon": float(snapped_start.get("lng", 0.0)),
                        "lat": float(snapped_start.get("lat", 0.0)),
                        "name": f"Snapped start ({snap.get('start_snap_distance_m', 0)}m)",
                        "type": "snapped",
                        "color": [120, 120, 255, 230],
                    },
                    {
                        "lon": float(snapped_end.get("lng", 0.0)),
                        "lat": float(snapped_end.get("lat", 0.0)),
                        "name": f"Snapped end ({snap.get('end_snap_distance_m', 0)}m)",
                        "type": "snapped",
                        "color": [120, 120, 255, 230],
                    },
                ]
            )
            layers.append(
                pdk.Layer(
                    "ScatterplotLayer",
                    data=snap_points,
                    get_position="[lon, lat]",
                    get_fill_color="color",
                    get_radius=12,
                    pickable=True,
                )
            )
            layers.append(
                pdk.Layer(
                    "PathLayer",
                    data=[
                        {"path": [[start_lng, start_lat], [snapped_start["lng"], snapped_start["lat"]]]},
                        {"path": [[end_lng, end_lat], [snapped_end["lng"], snapped_end["lat"]]]},
                    ],
                    get_path="path",
                    get_color=[180, 180, 180, 160],
                    width_scale=1,
                    width_min_pixels=3,
                    get_width=3,
                    pickable=False,
                )
            )
        if route_result and route_result.get("status") == "success":
            route_segments = route_result.get("route_segments", [])
            # If an older cached payload is in session, refresh once to get per-segment scores.
            if not route_segments:
                refreshed = get_path_sync(start_lat, start_lng, end_lat, end_lng)
                st.session_state["route_result"] = refreshed
                route_result = refreshed
                route_segments = route_result.get("route_segments", [])
            if route_segments:
                raw_scores = [float(seg.get("safety_score_100", 50.0)) for seg in route_segments]
                min_score = min(raw_scores) if raw_scores else 0.0
                max_score = max(raw_scores) if raw_scores else 100.0
                smoothed_scores = smooth_scores(raw_scores, blend_strength=0.65)
                segment_layer_data = []
                for idx, seg in enumerate(route_segments):
                    start = seg.get("from", {})
                    end = seg.get("to", {})
                    seg_score = smoothed_scores[idx]
                    display_score = normalize_route_score(seg_score, min_score, max_score)
                    segment_layer_data.append(
                        {
                            "path": [
                                [float(start.get("lng", 0.0)), float(start.get("lat", 0.0))],
                                [float(end.get("lng", 0.0)), float(end.get("lat", 0.0))],
                            ],
                            "color": score_to_rgb(display_score),
                            "name": seg.get("street_name", "Unknown"),
                            "street_name": seg.get("street_name", "Unknown"),
                            "distance_m": float(seg.get("distance_m", 0.0)),
                            "score_100": float(seg.get("safety_score_100", 0.0)),
                            "type": "route_segment",
                        }
                    )
                layers.append(
                    pdk.Layer(
                        "PathLayer",
                        data=segment_layer_data,
                        get_path="path",
                        get_color="color",
                        width_scale=2,
                        width_min_pixels=6,
                        get_width=6,
                        pickable=True,
                    )
                )
                st.caption(f"Route segment scores: {min_score:.1f} to {max_score:.1f} (contrast-enhanced view)")
            else:
                if len(route_result.get("path_coordinates", [])) <= 1:
                    st.info("Start and end are effectively the same point; no route segments to color.")
                else:
                    st.warning("Route found, but segment colors are unavailable. Reload app once, then compute again.")

        center_lat = (start_lat + end_lat) / 2.0
        center_lng = (start_lng + end_lng) / 2.0
        draw_map(
            layers,
            center_lat,
            center_lng,
            zoom=14,
            tooltip={"text": "{street_name}\nSegment safety: {score_100}\nDistance: {distance_m}m"},
        )

        if route_result:
            if route_result.get("status") == "success":
                st.success(
                    f"Route ready: {route_result.get('total_distance_m', 0)}m, "
                    f"weighted cost {route_result.get('total_weighted_cost', 0)}, "
                    f"avg safety {route_result.get('average_safety_score', 0)}."
                )
                path_points = route_result.get("path_points", [])
                if path_points:
                    route_steps = pd.DataFrame(path_points)[["point_type", "street_name", "lat", "lng"]]
                    st.dataframe(route_steps, use_container_width=True, hide_index=True)
            else:
                st.warning(f"⚠️ {route_result.get('error', 'Could not find a route.')}")
                if snap:
                    st.caption(
                        f"Snap distances: start {snap.get('start_snap_distance_m')}m, "
                        f"end {snap.get('end_snap_distance_m')}m (max allowed {snap.get('max_snap_distance_m')}m)"
                    )


def main():
    streets_df = load_streets()
    st.title("🛡️ SafeWalk Belfast Dashboard")
    st.markdown("Explore street safety and compute safety-optimized routes.")
    tab_original, tab_pathfinding = st.tabs(["Original", "Pathfinding"])

    with tab_original:
        render_original_tab(streets_df)

    with tab_pathfinding:
        render_pathfinding_tab(streets_df)


if __name__ == "__main__":
    main()
