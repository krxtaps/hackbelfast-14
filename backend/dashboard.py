import streamlit as st
import sqlite3
import pandas as pd
import asyncio
import pydeck as pdk
from pathlib import Path
from services.safety_engine import get_street_combined_score

st.set_page_config(page_title="SafeWalk Dashboard", page_icon="🛡️", layout="wide")

@st.cache_data
def load_streets():
    conn = sqlite3.connect("botanic.db")
    df = pd.read_sql("SELECT id, name, centroid_lat as lat, centroid_lng as lon FROM street ORDER BY name", conn)
    return df

def get_score_sync(street_id, time_str):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    return loop.run_until_complete(get_street_combined_score(street_id, time_str))

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


streets_df = load_streets()

st.title("🛡️ SafeWalk Belfast - Time-Based Safety Estimator")
st.markdown("Visualize how street safety scores adapt to real-time active business hours.")

col1, col2 = st.columns([1, 3])

with col1:
    st.subheader("Controls")
    
    default_idx = 0
    if "Botanic Avenue" in streets_df["name"].values:
        default_idx = int(streets_df[streets_df["name"] == "Botanic Avenue"].index[0])
        
    selected_street_name = st.selectbox("Select Street", streets_df["name"].unique(), index=default_idx)
    # GET ALL SEGMENTS FOR THIS STREET NAME!
    selected_street_ids = streets_df[streets_df["name"] == selected_street_name]["id"].tolist()
    
    st.markdown(f"*(Found {len(selected_street_ids)} segments for this street)*")
    
    st.markdown("---")
    st.markdown("**Simulate Time of Day**")
    time_preset = st.radio("Presets:", ["Daytime (14:00)", "Evening (21:30)", "Late Night (23:00)", "Deep Night (03:00)", "Custom"])
    
    if time_preset == "Custom":
        hour = st.slider("Hour", 0, 23, 14)
        minute = st.slider("Minute", 0, 45, 0, step=15)
        time_str = f"{hour:02d}:{minute:02d}"
    else:
        time_str = time_preset.split("(")[1].split(")")[0]

with col2:
    with st.spinner(f"Analyzing {len(selected_street_ids)} street segments..."):
        all_s_items_map = {}
        all_lines = []
        total_score = 0
        all_explanations = set()
        
        center_lat = 0
        center_lng = 0
        
        for sid in selected_street_ids:
            result = get_score_sync(sid, time_str)
            total_score += result.get("score", 0)
            
            lat = result.get("location", {}).get("lat", 0)
            lng = result.get("location", {}).get("lng", 0)
            center_lat += lat
            center_lng += lng
            
            
            # Aggregate geometry
            geometry = result.get("location", {}).get("geometry", {})
            
            seg_score = result.get("score", 0)
            seg_color = score_to_rgb(seg_score)
            
            if geometry.get("type") == "LineString":
                all_lines.append({"path": geometry["coordinates"], "color": seg_color, "score": seg_score})
            elif geometry.get("type") == "MultiLineString":
                for line in geometry["coordinates"]:
                    all_lines.append({"path": line, "color": seg_color, "score": seg_score})

                    
            # Aggregate Sanctuaries
            for s in result.get("sanctuaries", {}).get("items", []):
                if s.get("lat") and s.get("lng"):
                    # Deduplicate by coordinates
                    all_s_items_map[(s["lat"], s["lng"])] = s
                    
            # Aggregate Explanations
            for exp in result.get("explanations", []):
                all_explanations.add(exp)
        
        avg_score = int(total_score / len(selected_street_ids)) if selected_street_ids else 0
        center_lat /= len(selected_street_ids)
        center_lng /= len(selected_street_ids)
        s_items = list(all_s_items_map.values())
        
    
    # Create dynamic color styling for the metric display
    avg_rgb = score_to_rgb(avg_score)
    color_hex = f"#{avg_rgb[0]:02x}{avg_rgb[1]:02x}{avg_rgb[2]:02x}"
    
    st.markdown(f"### Average Safety Score @ {time_str}: <span style='color:{color_hex}'>{avg_score} / 100</span>", unsafe_allow_html=True)

    
    layers = []
    
    # Draw ALL Street Line Strings
    
    if all_lines:
        line_data = pd.DataFrame(all_lines)
        street_layer = pdk.Layer(
            "PathLayer",
            data=line_data,
            get_path="path",
            get_color="color", # DYNAMIC COLOR MAPPING!
            width_scale=2,
            width_min_pixels=5,
            get_width=5,
            pickable=True
        )
        layers.append(street_layer)

    # Draw ALL Sanctuaries
    if s_items:
        points = [{"lon": float(s["lng"]), "lat": float(s["lat"]), "name": s.get("name"), "type": s.get("type")} for s in s_items]
        point_data = pd.DataFrame(points)
        
        sanctuary_layer = pdk.Layer(
            "ScatterplotLayer",
            data=point_data,
            get_position="[lon, lat]",
            get_fill_color=[255, 255, 255, 255], # White dots for Sanctuaries
            get_line_color=[0, 0, 0, 255],
            get_radius=12, 
            pickable=True,
            stroked=True,
            get_line_width=2
        )
        layers.append(sanctuary_layer)


    if layers and center_lat and center_lng:
        view_state = pdk.ViewState(
            latitude=center_lat,
            longitude=center_lng,
            zoom=15,
            pitch=0
        )
        
        st.pydeck_chart(pdk.Deck(
            layers=layers,
            initial_view_state=view_state,
            tooltip={"text": "{name}\n{type}"}
        ))
    else:
        st.warning("⚠️ No data available to map.")

    if s_items:
        st.success(f"{len(s_items)} Safe Sanctuaries are currently OPEN across the entire street.")
    else:
        st.warning("⚠️ No Safe Sanctuaries are open on this street right now.")

    with st.expander("Detailed Score Breakdown", expanded=True):
        def sort_key(x):
            if x.startswith("---"): return "0" + x
            x_lower = x.lower()
            if "crime" in x_lower or "anti-social" in x_lower: return "1" + x
            if "sanctuary" in x_lower: return "2" + x
            if "amenity" in x_lower: return "3" + x
            if "lamp" in x_lower or "infrastructure" in x_lower or "class" in x_lower: return "4" + x
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
            elif "lamp" in reason.lower() or "infrastructure" in reason.lower() or "class" in reason.lower() or "context" in reason.lower():
                st.write(f"💡 {reason}")
            else:
                st.write(f"ℹ️ {reason}")
