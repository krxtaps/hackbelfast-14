import asyncio
import heapq
import math
import pickle
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from maps.loader import load_botanic_streets
from services.geo import haversine_m, min_distance_to_geometry
from services.safety_engine import get_street_combined_score


CACHE_FORMAT_VERSION = 2


class PathfindingService:
    """
    Service to calculate the safest path between two points using Dijkstra's algorithm.
    The 'weight' of each edge is a function of its physical length and its safety score.
    """

    def __init__(self):
        # node (lat, lng) -> list of (neighbor_node, weight, metadata)
        self.graph: Dict[
            Tuple[float, float], List[Tuple[Tuple[float, float], float, Dict[str, Any]]]
        ] = {}
        self._is_initialized = False
        self._node_index: List[Tuple[float, float]] = []
        self._nearest_node_max_distance_m = 750.0
        self._street_score_cache: Dict[str, float] = {}
        self._street_name_cache: Dict[str, str] = {}
        self._nearest_cache: Dict[Tuple[float, float], Optional[Tuple[float, float]]] = {}
        self._nearest_cache_with_dist: Dict[
            Tuple[float, float], Tuple[Optional[Tuple[float, float]], float]
        ] = {}
        self._edge_lookup: Dict[Tuple[Tuple[float, float], Tuple[float, float]], Dict[str, Any]] = {}
        self._cache_dir = Path(__file__).resolve().parent.parent / ".cache"
        self._graph_cache_path = self._cache_dir / "pathfinding_graph.pkl"
        # Merge nodes that are within ~1m to improve connectivity
        self._node_precision_decimals = 5

    def _canon_node(self, lat: float, lng: float) -> Tuple[float, float]:
        """Canonicalize nodes to reduce fragmentation (rounding ~1m)."""
        return (round(lat, self._node_precision_decimals), round(lng, self._node_precision_decimals))

    def _resolve_to_nearest_street_vertex(
        self, lat: float, lng: float, max_distance_m: float
    ) -> Dict[str, Any]:
        """
        Resolves an arbitrary point to the nearest street feature and then to the nearest
        vertex on that street geometry. Returns dict with resolved point + street context.
        """
        streets = load_botanic_streets() or {}
        features = streets.get("features", [])
        if not features:
            return {"error": "Street data not available"}

        best_feature = None
        best_dist = float("inf")
        for f in features:
            geom = f.get("geometry", {})
            d = min_distance_to_geometry(lat, lng, geom)
            if d < best_dist:
                best_dist = d
                best_feature = f

        if best_feature is None:
            return {"error": "No streets found"}

        props = best_feature.get("properties", {})
        street_id = props.get("id")
        street_name = props.get("name") or self._get_street_name(street_id)

        if best_dist > max_distance_m:
            return {
                "error": "No nearby street within max distance",
                "distance_m": round(best_dist, 2),
                "max_distance_m": max_distance_m,
                "nearest_street": {"street_id": street_id, "street_name": street_name},
            }

        # Find nearest vertex on the street geometry
        geom = best_feature.get("geometry", {})
        coords = geom.get("coordinates", [])
        geo_type = geom.get("type")
        best_vertex = None
        best_vertex_dist = float("inf")

        def consider_vertex(lng_v: float, lat_v: float) -> None:
            nonlocal best_vertex, best_vertex_dist
            d = haversine_m(lat, lng, lat_v, lng_v)
            if d < best_vertex_dist:
                best_vertex_dist = d
                best_vertex = (lat_v, lng_v)

        if geo_type == "LineString":
            for lng_v, lat_v in coords:
                consider_vertex(lng_v, lat_v)
        elif geo_type == "MultiLineString":
            for line in coords:
                for lng_v, lat_v in line:
                    consider_vertex(lng_v, lat_v)

        if best_vertex is None:
            return {"error": "Street geometry had no vertices"}

        vlat, vlng = best_vertex
        return {
            "status": "resolved",
            "requested": {"lat": lat, "lng": lng},
            "street": {"street_id": street_id, "street_name": street_name},
            "resolved": {"lat": vlat, "lng": vlng},
            "distance_to_street_m": round(best_dist, 2),
            "distance_to_vertex_m": round(best_vertex_dist, 2),
        }

    def _street_data_signature(self, streets_geojson: Dict[str, Any]) -> str:
        """Compact signature to invalidate stale graph cache."""
        features = streets_geojson.get("features", [])
        if not features:
            return "empty"
        ids = [f.get("properties", {}).get("id", "") for f in features]
        first_id = ids[0] if ids else ""
        last_id = ids[-1] if ids else ""
        return f"{len(features)}:{first_id}:{last_id}"

    def _try_load_cached_graph(self, signature: str) -> bool:
        if not self._graph_cache_path.exists():
            return False
        try:
            with self._graph_cache_path.open("rb") as f:
                payload = pickle.load(f)
            if payload.get("cache_version") != CACHE_FORMAT_VERSION:
                return False
            if payload.get("signature") != signature:
                return False

            self.graph = payload.get("graph", {})
            self._node_index = payload.get("node_index", [])
            self._street_score_cache = payload.get("street_score_cache", {})
            self._edge_lookup = payload.get("edge_lookup", {})
            self._street_name_cache = payload.get("street_name_cache", {})
            self._is_initialized = bool(self.graph)
            return self._is_initialized
        except Exception:
            return False

    def _persist_graph_cache(self, signature: str) -> None:
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        payload = {
            "cache_version": CACHE_FORMAT_VERSION,
            "signature": signature,
            "graph": self.graph,
            "node_index": self._node_index,
            "street_score_cache": self._street_score_cache,
            "street_name_cache": self._street_name_cache,
            "edge_lookup": self._edge_lookup,
        }
        with self._graph_cache_path.open("wb") as f:
            pickle.dump(payload, f, protocol=pickle.HIGHEST_PROTOCOL)

    async def _preload_street_scores(self, features: List[Dict[str, Any]], concurrency: int = 24) -> None:
        """Preloads full street scores concurrently to reduce graph init time."""
        sem = asyncio.Semaphore(concurrency)
        street_ids = {
            feature.get("properties", {}).get("id")
            for feature in features
            if feature.get("properties", {}).get("id")
        }

        async def load_score(street_id: str) -> None:
            if street_id in self._street_score_cache:
                return
            async with sem:
                try:
                    score_data = await get_street_combined_score(street_id)
                    self._street_score_cache[street_id] = float(score_data.get("score", 50)) / 100.0
                except Exception:
                    self._street_score_cache[street_id] = 0.5

        await asyncio.gather(*(load_score(street_id) for street_id in street_ids))

    def _get_street_name(self, street_id: Optional[str]) -> str:
        if not street_id:
            return "Unknown"
        if street_id in self._street_name_cache:
            return self._street_name_cache[street_id]
        streets_geojson = load_botanic_streets() or {}
        for feature in streets_geojson.get("features", []):
            props = feature.get("properties", {})
            sid = props.get("id")
            if sid:
                self._street_name_cache[sid] = props.get("name") or "Unknown"
        return self._street_name_cache.get(street_id, "Unknown")

    def _haversine_distance(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """Calculates the great-circle distance between two points in meters."""
        R = 6371000  # Earth radius in meters
        phi1, phi2 = math.radians(lat1), math.radians(lat2)
        dphi = math.radians(lat2 - lat1)
        dlambda = math.radians(lon2 - lon1)

        a = (math.sin(dphi / 2)**2 +
             math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2)**2)
        c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
        return R * c

    def _iter_lines(self, geometry: Dict[str, Any]) -> List[List[List[float]]]:
        """Normalizes GeoJSON geometry to a list of line coordinate arrays."""
        geo_type = geometry.get("type")
        coords = geometry.get("coordinates", [])
        if geo_type == "LineString":
            return [coords] if isinstance(coords, list) else []
        if geo_type == "MultiLineString":
            return coords if isinstance(coords, list) else []
        return []

    async def initialize_graph(self, force_rebuild: bool = False):
        """
        Constructs the graph from street data. 
        In a production environment, this would be pre-computed and stored in a spatial DB.
        """
        if self._is_initialized:
            return

        # Load streets from the data source
        streets_geojson = load_botanic_streets()
        if not streets_geojson:
            return
        signature = self._street_data_signature(streets_geojson)
        if not force_rebuild and self._try_load_cached_graph(signature):
            return
        # reset caches that depend on node topology
        self.graph = {}
        self._edge_lookup = {}
        self._node_index = []
        self._nearest_cache_with_dist = {}
        features = streets_geojson.get("features", [])
        await self._preload_street_scores(features)
        for feature in features:
            props = feature.get("properties", {})
            sid = props.get("id")
            if sid:
                self._street_name_cache[sid] = props.get("name") or "Unknown"

        edge_map: Dict[
            Tuple[Tuple[float, float], Tuple[float, float]],
            Tuple[float, Dict[str, Any]],
        ] = {}

        for feature in features:
            properties = feature.get("properties", {})
            street_id = properties.get("id")
            if not street_id:
                continue

            # Use full hybrid street scoring with per-street cache.
            safety_score = self._street_score_cache.get(street_id, 0.5)

            # Define how much unsafe streets penalize the path cost
            # A score of 0.0 (unsafe) will increase weight by up to 5x distance
            SAFETY_PENALTY_MULTIPLIER = 5.0
            safety_multiplier = 1.0 + (1.0 - safety_score) * (SAFETY_PENALTY_MULTIPLIER - 1.0)

            geometry = feature.get("geometry", {})
            for coords in self._iter_lines(geometry):
                if len(coords) < 2:
                    continue

                for i in range(len(coords) - 1):
                    # GeoJSON uses [longitude, latitude]
                    lon1, lat1 = coords[i]
                    lon2, lat2 = coords[i + 1]

                    node1 = self._canon_node(lat1, lon1)
                    node2 = self._canon_node(lat2, lon2)

                    dist = self._haversine_distance(lat1, lon1, lat2, lon2)
                    if dist <= 0:
                        continue

                    # The weight is the "cost" of traversing this edge.
                    # High safety -> low weight; Low safety -> high weight.
                    weight = dist * safety_multiplier

                    metadata = {
                        "street_id": street_id,
                        "street_name": self._get_street_name(street_id),
                        "safety_score": safety_score,
                        "distance": dist,
                    }
                    key = (node1, node2) if node1 <= node2 else (node2, node1)
                    existing = edge_map.get(key)
                    if existing is None or weight < existing[0]:
                        edge_map[key] = (weight, metadata)

        for (node1, node2), (weight, metadata) in edge_map.items():
            if node1 not in self.graph:
                self.graph[node1] = []
            if node2 not in self.graph:
                self.graph[node2] = []
            self.graph[node1].append((node2, weight, metadata))
            self.graph[node2].append((node1, weight, metadata))
            self._edge_lookup[(node1, node2)] = metadata
            self._edge_lookup[(node2, node1)] = metadata

        self._node_index = list(self.graph.keys())
        self._is_initialized = True
        self._persist_graph_cache(signature)

    def _find_nearest_node_with_distance(
        self, lat: float, lng: float
    ) -> Tuple[Optional[Tuple[float, float]], float]:
        """Returns (nearest_node, distance_m)."""
        if not self._node_index:
            return None, float("inf")

        cache_key = (round(lat, 5), round(lng, 5))
        if cache_key in self._nearest_cache_with_dist:
            return self._nearest_cache_with_dist[cache_key]

        min_dist = float("inf")
        nearest_node: Optional[Tuple[float, float]] = None
        for node in self._node_index:
            d = self._haversine_distance(lat, lng, node[0], node[1])
            if d < min_dist:
                min_dist = d
                nearest_node = node

        result = (
            (nearest_node, min_dist)
            if min_dist < self._nearest_node_max_distance_m
            else (None, min_dist)
        )
        self._nearest_cache_with_dist[cache_key] = result
        return result

    async def find_safest_path(
        self,
        start_lat: float,
        start_lng: float,
        end_lat: float,
        end_lng: float,
        *,
        max_snap_distance_m: float = 50.0,
    ) -> Dict[str, Any]:
        """
        Finds the path with the lowest 'cost' (safety-weighted distance).
        """
        if not self._is_initialized:
            await self.initialize_graph()

        # First resolve inputs to nearest street (<= max_snap_distance_m) and use that for routing.
        start_res = self._resolve_to_nearest_street_vertex(start_lat, start_lng, max_snap_distance_m)
        if "error" in start_res:
            return {"error": "Start point could not be matched to a street within range.", "resolve": {"start": start_res}}
        end_res = self._resolve_to_nearest_street_vertex(end_lat, end_lng, max_snap_distance_m)
        if "error" in end_res:
            return {"error": "End point could not be matched to a street within range.", "resolve": {"end": end_res}}

        resolved_start = start_res["resolved"]
        resolved_end = end_res["resolved"]

        # Find the nearest nodes in the graph to the resolved coordinates
        start_node, start_snap_m = self._find_nearest_node_with_distance(resolved_start["lat"], resolved_start["lng"])
        end_node, end_snap_m = self._find_nearest_node_with_distance(resolved_end["lat"], resolved_end["lng"])

        if not start_node or not end_node:
            return {"error": "Could not find starting or ending points in the street network."}

        # If resolved point still can't snap to a node (should be rare), fail.
        if start_snap_m > max_snap_distance_m or end_snap_m > max_snap_distance_m:
            return {
                "error": "Resolved start/end still too far from routable nodes.",
                "resolve": {"start": start_res, "end": end_res},
                "snap": {
                    "max_snap_distance_m": max_snap_distance_m,
                    "start_snap_distance_m": round(start_snap_m, 2),
                    "end_snap_distance_m": round(end_snap_m, 2),
                    "snapped_start": {"lat": start_node[0], "lng": start_node[1]},
                    "snapped_end": {"lat": end_node[0], "lng": end_node[1]},
                },
            }

        requested_distance_m = self._haversine_distance(start_lat, start_lng, end_lat, end_lng)
        if start_node == end_node and requested_distance_m > 25.0:
            return {
                "error": "Start/end snapped to same network point; route would be misleading.",
                "resolve": {"start": start_res, "end": end_res},
                "snap": {
                    "max_snap_distance_m": max_snap_distance_m,
                    "start_snap_distance_m": round(start_snap_m, 2),
                    "end_snap_distance_m": round(end_snap_m, 2),
                    "snapped_start": {"lat": start_node[0], "lng": start_node[1]},
                    "snapped_end": {"lat": end_node[0], "lng": end_node[1]},
                },
            }

        # A* Algorithm
        # f = g + h  where:
        #   g = cumulative safety-weighted cost so far
        #   h = admissible heuristic — straight-line haversine distance to goal
        #       (always ≤ true remaining cost, so A* stays optimal)
        # priority_queue stores (f_cost, g_cost, current_node, path_taken)
        def heuristic(node: Tuple[float, float]) -> float:
            return haversine_m(node[0], node[1], end_node[0], end_node[1])

        g_start = 0.0
        pq = [(g_start + heuristic(start_node), g_start, start_node, [start_node])]
        # visited maps node → best g_cost seen so far
        visited: Dict[Tuple[float, float], float] = {start_node: 0.0}

        while pq:
            (_, current_cost, current_node, path) = heapq.heappop(pq)

            if current_node == end_node:
                total_distance = 0.0
                path_safety_scores: List[float] = []
                route_segments: List[Dict[str, Any]] = []
                for idx in range(len(path) - 1):
                    n1 = path[idx]
                    n2 = path[idx + 1]
                    metadata = self._edge_lookup.get((n1, n2), {})
                    segment_distance = float(metadata.get("distance", 0.0))
                    segment_safety = float(metadata.get("safety_score", 0.5))
                    total_distance += segment_distance
                    path_safety_scores.append(segment_safety)
                    route_segments.append(
                        {
                            "from": {"lat": n1[0], "lng": n1[1]},
                            "to": {"lat": n2[0], "lng": n2[1]},
                            "street_id": metadata.get("street_id"),
                            "street_name": self._get_street_name(metadata.get("street_id")),
                            "distance_m": round(segment_distance, 2),
                            "safety_score": round(segment_safety, 3),
                            "safety_score_100": round(segment_safety * 100.0, 1),
                        }
                    )

                path_points: List[Dict[str, Any]] = []
                for idx, node in enumerate(path):
                    prev_seg = route_segments[idx - 1] if idx > 0 and idx - 1 < len(route_segments) else None
                    next_seg = route_segments[idx] if idx < len(route_segments) else None
                    primary_seg = next_seg or prev_seg or {}
                    path_points.append(
                        {
                            "lat": node[0],
                            "lng": node[1],
                            "street_id": primary_seg.get("street_id"),
                            "street_name": self._get_street_name(primary_seg.get("street_id")),
                            "point_type": (
                                "start"
                                if idx == 0
                                else "end"
                                if idx == len(path) - 1
                                else "intermediate"
                            ),
                        }
                    )
                return {
                    "status": "success",
                    "total_weighted_cost": round(current_cost, 2),
                    "total_distance_m": round(total_distance, 2),
                    "average_safety_score": round(
                        (sum(path_safety_scores) / len(path_safety_scores)) if path_safety_scores else 0.0,
                        3,
                    ),
                    "requested_start": {"lat": start_lat, "lng": start_lng},
                    "requested_end": {"lat": end_lat, "lng": end_lng},
                    "resolve": {"start": start_res, "end": end_res},
                    "snap": {
                        "max_snap_distance_m": max_snap_distance_m,
                        "start_snap_distance_m": round(start_snap_m, 2),
                        "end_snap_distance_m": round(end_snap_m, 2),
                    },
                    "snapped_start": {"lat": start_node[0], "lng": start_node[1]},
                    "snapped_end": {"lat": end_node[0], "lng": end_node[1]},
                    "path_coordinates": [[lat, lng] for lat, lng in path],
                    "path_points": path_points,
                    "route_segments": route_segments,
                    "safety_optimized": True,
                    "algorithm": "a_star",
                }

            if current_cost > visited.get(current_node, float('inf')):
                continue

            for neighbor, weight, metadata in self.graph.get(current_node, []):
                new_g = current_cost + weight

                if new_g < visited.get(neighbor, float('inf')):
                    visited[neighbor] = new_g
                    new_path = path + [neighbor]
                    f = new_g + heuristic(neighbor)
                    heapq.heappush(pq, (f, new_g, neighbor, new_path))

        return {"error": "No safe path found connecting the requested points."}

    def _find_nearest_node(self, lat: float, lng: float) -> Optional[Tuple[float, float]]:
        """Finds the closest node in the graph to the given coordinates."""
        if not self._node_index:
            return None
        cache_key = (round(lat, 5), round(lng, 5))
        if cache_key in self._nearest_cache:
            return self._nearest_cache[cache_key]

        min_dist = float('inf')
        nearest_node = None

        for node in self._node_index:
            d = self._haversine_distance(lat, lng, node[0], node[1])
            if d < min_dist:
                min_dist = d
                nearest_node = node

        # Threshold to avoid snapping to completely unrelated parts of the city.
        result = nearest_node if min_dist < self._nearest_node_max_distance_m else None
        self._nearest_cache[cache_key] = result
        return result
