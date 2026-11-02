# Exclusion zones

Import a map/CSV into planning, then use **Exclusion zones** in the map toolbar.
Click **Add zone**, click polygon vertices, and click the first vertex or press
Enter to finish. Esc cancels a draft. Select a zone to delete it, or undo the
last saved change. Up to 20 simple polygons, each with 3–64 vertices, are supported.

Zones are shown in translucent red. They use world coordinates in metres and
are unavailable in read-only file previews or pixel-only background previews.
Closing the tool restores the existing pan, Ctrl selection, waypoint and speed
editing interactions. No additional sidebar or chart space is reserved.

Use the existing calculation button to apply changes. Both iterative QP and
the original SLSQP solver treat zones as hard obstacles, with the same vehicle
footprint and safety margin used for physical boundaries. They attempt to repair
an initial reference crossing a zone; no feasible route is guaranteed. A route
failing the final dense checks is never exported as a successful result.

The original image, YAML, CSV corridor and remote files are unchanged. Settings
are saved atomically under `.cache/exclusions/`, keyed by map image, occupancy,
resolution and origin. Without a georeferenced map, the key uses the CSV corridor.
Matching inputs restore zones on import. Concurrent edits use revision checks.
Each calculation freezes its own zone snapshot; the result report, comparison
image and result ZIP include the applied zones (`exclusion_zones.json`). Settings
and generated results remain excluded from Git.

An earlier result is marked stale after a zone change. Manually editing a path
after calculation still requires revalidation, as before. These are offline
planning constraints, not a live obstacle layer sent to the vehicle controller.
Minimum curvature is not a minimum-lap-time objective.
