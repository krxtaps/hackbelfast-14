import re
from pathlib import Path

osm_file = Path("scripts/ingest_osm_pois.py")
content = osm_file.read_text()

new_query = """def _build_overpass_query() -> str:
    \"\"\"
    Uses the administrative area named "Belfast" and fetches nodes/ways/relations.
    \"\"\"
    return \"\"\"
    [out:json][timeout:60];
    area["name"="Belfast"]["boundary"="administrative"]->.searchArea;
    (
      nwr["shop"="convenience"](area.searchArea);
      nwr["shop"="supermarket"](area.searchArea);
      nwr["amenity"="pharmacy"](area.searchArea);
      nwr["amenity"="bar"](area.searchArea);
      nwr["amenity"="pub"](area.searchArea);
      nwr["amenity"="nightclub"](area.searchArea);
      nwr["amenity"="police"](area.searchArea);
      nwr["amenity"="hospital"](area.searchArea);
      nwr["amenity"="clinic"](area.searchArea);
      nwr["amenity"="doctors"](area.searchArea);
      nwr["amenity"="library"](area.searchArea);
      nwr["amenity"="university"](area.searchArea);
      nwr["amenity"="college"](area.searchArea);
      nwr["leisure"="fitness_centre"](area.searchArea);
      nwr["tourism"="hotel"](area.searchArea);
      nwr["tourism"="hostel"](area.searchArea);
      nwr["amenity"="cafe"](area.searchArea);
      nwr["amenity"="fast_food"](area.searchArea);
      nwr["amenity"="restaurant"](area.searchArea);
      nwr["shop"="clothes"](area.searchArea);
    );
    out center tags;
    \"\"\"
"""

content = re.sub(r'def _build_overpass_query.*?out center tags;\n    """', new_query, content, flags=re.DOTALL)

new_extract = """def _extract_category(tags: Dict[str, Any]) -> str:
    shop = tags.get("shop")
    amenity = tags.get("amenity")
    leisure = tags.get("leisure")
    tourism = tags.get("tourism")
    
    if shop: return shop
    if amenity: return amenity
    if leisure == "fitness_centre": return "gym"
    if tourism in {"hotel", "hostel"}: return tourism
    return "unknown"
"""

content = re.sub(r'def _extract_category.*?return "unknown"', new_extract, content, flags=re.DOTALL)

osm_file.write_text(content)
