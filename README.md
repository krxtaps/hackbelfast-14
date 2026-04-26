# BTWaypoint

BTWaypoint is a real-time safer-navigation system for Belfast. Instead of optimizing only for the shortest path, it evaluates live safety conditions and recommends routes that adapt to what is happening in the city right now.

The project combines map data, crime signals, lighting context, open venues, local news, and user feedback to build a routing system that is both safety-aware and explainable.

## Motivation

Nighttime safety is not static. Conditions change across time of day, location, and recent local events, yet many navigation systems still rely on historical summaries or static hotspot views.

BTWaypoint was built to address that gap. The goal is to help users answer a practical question: not just how to get from A to B, but how to get there more safely, with some understanding of why a route is being recommended.

## What BTWaypoint does

BTWaypoint assigns every street segment a dynamic safety score from 0 to 100. That score is then used directly inside the routing engine so that the chosen path reflects both geography and real-world risk.

The system updates on a regular cycle and can react to:

- Recent incidents.
- Environmental context such as street lighting.
- Whether nearby sanctuaries or useful venues are currently open.
- Signals extracted from local news.
- User feedback submitted through a pseudo-anonymous Solana-based flow.

As a result, the app may recommend a longer route if it appears materially safer than the shortest available path.

## Core ideas

BTWaypoint is built around a few key ideas:

- Safety should be part of pathfinding, not just a layer shown on top of a map.
- Local risk should be measured at street-segment level, not only at area level.
- Routing decisions should be explainable to the user.
- Time of day matters.
- Community feedback can improve the model when handled carefully.

## System architecture

At a high level, BTWaypoint works as a multi-stage pipeline:

1. Build a routable street graph from map data.
2. Split streets into smaller segments for localized scoring.
3. Enrich each segment with crime, venue, environmental, news, and feedback signals.
4. Normalize those signals into a safety score.
5. Use that score inside a safety-aware A* routing process.
6. Return the route with reasoning, not just a path line.

## Data flow

### 1. Street network ingestion

The routing layer starts with OpenStreetMap and Overpass-derived street geometry. These sources provide the structure needed to represent Belfast as a graph rather than just a visual map.

Because map geometry often comes in fragmented pieces, BTWaypoint performs a join step to reconnect smaller chunks into coherent streets while keeping finer internal segments for scoring accuracy.

### 2. Street segmentation

Each street is split into smaller segments so risk can be evaluated locally. This is important because two parts of the same road may have very different safety characteristics depending on incidents, lighting, or nearby support locations.

These segments become the basic units used by the scoring engine.

### 3. Crime data pipeline

The system uses PSNI data for recent incident updates and OpenNI for broader supporting context. For each segment, nearby incidents are checked within a local radius and weighted based on both severity and proximity.

This means more serious offenses have a stronger effect on the score, and incidents closer to a segment influence routing more than distant ones.

### 4. Environmental data

BTWaypoint also integrates environmental context, especially street-light location and status. This matters because route safety at night depends on visibility and practical conditions, not only on recorded crime.

Environmental signals are blended with the rest of the data rather than treated as a separate view.

### 5. Sanctuary and venue intelligence

A major feature of the system is the idea of **sanctuaries**. These are trusted or useful nearby places that can improve the safety of a route when they are open and realistically available.

Venue data is sourced using both Overpass and Foursquare. Overpass is useful for map-level spatial information, while Foursquare provides broader place coverage and better venue metadata.

The system also takes time of day into account, so a venue that helps at 2 PM may not help at 2 AM if it is closed.

### 6. News pipeline and LangChain

Local Belfast news is fetched through an API, but raw headlines are not directly useful to a routing engine. They are unstructured, noisy, and written for human attention rather than machine reasoning.

This is where LangChain comes in.

LangChain acts as the orchestration layer between raw news input and the scoring model. It coordinates the LLM-powered processing step that determines:

- Whether a headline is relevant to public safety.
- What kind of incident or risk it describes.
- Where the event appears to be happening.

The project uses LangChain together with a Featherless-served DeepSeek model to turn unstructured headlines into structured safety signals. Those results are then stored and fed into the segment-level scoring pipeline.

This makes local news a real part of the routing system rather than just an informational side feature.

### 7. Solana-based user feedback

BTWaypoint also takes user feedback through a Solana-based pseudo-anonymous flow. This gives the platform a privacy-preserving way to collect ground-level signals from people who are actually using the system.

That feedback can be used to refine risk in near real time, especially in cases where official datasets or news sources have not yet caught up to local conditions.

### 8. Background workers and caching

A fully live implementation would be too expensive if every route request triggered direct queries for every segment and every external source.

To avoid that, BTWaypoint uses background workers to update relevant data on a regular cycle. These workers fetch new incident updates, process fresh news through LangChain, refresh derived segment data, and cache the outputs so route requests can be answered quickly.

This keeps the system responsive while still allowing near-real-time updates.

### 9. Routing engine

Once all segment data has been prepared, the road network is modeled as a graph using NetworkX. A* is then used to search for routes, but unlike traditional shortest-path routing, safety is part of the heuristic.

This means the engine can prefer a longer route when it appears safer overall.

### 10. Explanation layer

The output of BTWaypoint is not just a line on a map. Each route also includes a safety score and reasoning so the user can understand the basis for the recommendation.

That transparency is important because safer routing is fundamentally a trust problem as much as a technical one.

## Data sources

BTWaypoint uses multiple sources because no single dataset captures urban safety well enough on its own.

| Source | Purpose |
|---|---|
| OpenStreetMap / Overpass | Street and path geometry for graph construction |
| PSNI | Recent incident updates |
| OpenNI | Supporting open data, including lighting and broader context |
| Foursquare | Venue metadata and sanctuary enrichment |
| Local news API | Real-time local safety context |
| LangChain + DeepSeek | News relevance, classification, and extraction |
| Solana feedback flow | Pseudo-anonymous user input |
| User feedback loop | Ongoing refinement of risk scoring |

## Data cleaning and normalization

Data quality is one of the hardest parts of the system. The sources used by BTWaypoint differ in freshness, structure, and reliability, so the platform includes cleaning and normalization before scoring.

### Venue cleaning

Venue data can be stale or incomplete. Some places may be closed, missing opening hours, or badly matched to map geometry.

To deal with this, BTWaypoint filters venue records based on freshness and correlates place information across sources before treating a venue as an active sanctuary.

### Geometry cleaning

Street geometry from Overpass often arrives in small pieces. These fragments need to be reconnected into meaningful street structures for routing, while still preserving the smaller chunks needed for accurate backend scoring.

### News normalization

News headlines are noisy and ambiguous. The LangChain pipeline converts them into structured fields such as relevance, approximate location, and incident category so they can be used inside the scoring model.

### Feedback normalization

User feedback is valuable, but it should not be treated as unquestioned truth. A robust implementation would weight feedback based on recency, consistency, local agreement, and overlap with other signals before changing a risk score significantly.

### Refresh-aware caching

The system stores refreshed intermediate results rather than recomputing everything on every route request. This improves both performance and consistency.

## Safety scoring

Each street segment receives a score from 0 to 100. The score reflects a combination of:

- Nearby incidents.
- Severity weighting of incidents.
- Lighting and environmental conditions.
- Availability of sanctuaries and open venues.
- Time-of-day context.
- Local news signals.
- User feedback.

The project also uses logarithmic scaling relative to local patterns and wider city context so the score remains interpretable even when raw incident density varies sharply.

## Routing logic

The routing engine is built with NetworkX and A*. The important difference from a standard route planner is that safety is embedded into the decision process itself.

At intersections and other meaningful choice points, the algorithm compares candidate paths using safety-aware costs. If a direct route passes through segments that score poorly, the engine can prefer a safer detour.

The graph is also optimized by removing redundant nodes between intersections where no meaningful decision is needed, which helps improve performance.

## Tools used

| Tool / Service | Role |
|---|---|
| OpenStreetMap | Base map data |
| Overpass | Geospatial extraction |
| NetworkX | Graph modeling and traversal |
| A* | Route search |
| Polars | High-performance data processing |
| PSNI API | Incident ingestion |
| OpenNI | Lighting and supporting open data |
| Foursquare | Venue enrichment |
| LangChain | LLM workflow orchestration for news analysis |
| Featherless / DeepSeek | Headline classification and extraction |
| Solana | Pseudo-anonymous feedback submission |
| Background workers | Periodic refresh and caching |

## Why this approach matters

BTWaypoint does more than display safety information on a map. It turns safety context into a routing decision.

That makes the system more adaptive than a static hotspot view and more useful than a route planner that only optimizes for speed or distance.

## Future work

Natural next steps for the project include:

- Expanding beyond Belfast.
- Improving trust and weighting models for user feedback.
- Adding richer environmental inputs such as CCTV-related context.
- Building a stronger mobile experience.
- Creating route explanation views that show exactly how each signal influenced the final result.
