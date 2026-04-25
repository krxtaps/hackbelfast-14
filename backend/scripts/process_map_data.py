import json
import uuid
from pathlib import Path

def process_map_data():
    project_root = Path(__file__).parent.parent
    raw_file = project_root / "maps" / "raw" / "queens-bfs-streets.geojson"
    seed_dir = project_root / "maps" / "seed"
    seed_file = seed_dir / "botanic-streets.seed.geojson"

    # Ensure output directory exists
    seed_dir.mkdir(parents=True, exist_ok=True)

    if not raw_file.exists():
        print(f"Error: Raw file not found at {raw_file}")
        return

    print(f"Reading raw file: {raw_file}")
    with open(raw_file, "r", encoding="utf-8") as f:
        data = json.load(f)

    if data.get("type") != "FeatureCollection":
        print("Error: Input is not a valid FeatureCollection")
        return

    features = data.get("features", [])
    total_raw_features = len(features)
    print(f"Found {total_raw_features} features in raw file.")

    kept_features = []
    retained_highways = set()
    suspicious_issues = []

    valid_highways = {
        "primary", "secondary", "tertiary", "residential", 
        "footway", "pedestrian", "path", "steps"
    }

    for idx, feature in enumerate(features):
        geometry = feature.get("geometry")
        properties = feature.get("properties", {})

        # Validation checks
        if not geometry:
            suspicious_issues.append(f"Feature {idx}: Missing geometry")
            continue
        
        geom_type = geometry.get("type")
        if geom_type not in ("LineString", "MultiLineString"):
            continue

        coordinates = geometry.get("coordinates")
        if not coordinates:
            suspicious_issues.append(f"Feature {idx}: Empty coordinates")
            continue

        highway = properties.get("highway")
        if highway not in valid_highways:
            continue

        # Valid feature to keep
        retained_highways.add(highway)

        # Build normalized properties
        osm_id = feature.get("id") or properties.get("osm_way_id") or properties.get("osm_id")
        
        normalized_properties = {
            "id": f"botanic_{uuid.uuid4().hex[:8]}", # Stable internal id
            "name": properties.get("name"),
            "highway": highway,
            "area": "botanic",
            "source": "osm_overpass",
            "seed_version": 1,
            "osm_identity": osm_id
        }

        # Remove None values
        normalized_properties = {k: v for k, v in normalized_properties.items() if v is not None}

        kept_features.append({
            "type": "Feature",
            "geometry": geometry,
            "properties": normalized_properties
        })

    # Prepare output data
    output_data = {
        "type": "FeatureCollection",
        "features": kept_features
    }

    print(f"Writing {len(kept_features)} features to {seed_file}")
    with open(seed_file, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    # Print summary
    print("\n--- Summary ---")
    print(f"Raw file: {raw_file.relative_to(project_root)}")
    print(f"Raw features count: {total_raw_features}")
    print(f"Kept features count: {len(kept_features)}")
    print(f"Highway types retained: {', '.join(sorted(retained_highways))}")
    if suspicious_issues:
        print(f"Suspicious issues found: {len(suspicious_issues)} (First 5: {suspicious_issues[:5]})")
    else:
        print("No suspicious issues found.")
    print("----------------")

if __name__ == "__main__":
    process_map_data()
