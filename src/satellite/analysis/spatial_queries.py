"""
PostGIS Spatial Queries Module

Manages spatial data in PostGIS and performs:
- Proximity analysis (samples near rivers, faults, roads)
- Buffer zone generation
- Spatial joins between sample points and raster results
- Area-of-interest queries
"""
import logging
from typing import Dict, List, Tuple, Optional, Any

import numpy as np

from ..utils.config import PostGISConfig, OUTPUT_DIR

logger = logging.getLogger("afrimine.satellite.spatial_queries")

# SQL table creation
INIT_SQL = """
CREATE EXTENSION IF NOT EXISTS postgis;
CREATE EXTENSION IF NOT EXISTS postgis_raster;

CREATE TABLE IF NOT EXISTS sample_points (
    id SERIAL PRIMARY KEY,
    name VARCHAR(255),
    geom GEOMETRY(Point, 4326),
    collection_date DATE,
    mineral_type VARCHAR(100),
    notes TEXT,
    properties JSONB
);

CREATE TABLE IF NOT EXISTS lineaments (
    id SERIAL PRIMARY KEY,
    geom GEOMETRY(LineString, 4326),
    length_m DOUBLE PRECISION,
    orientation DOUBLE PRECISION,
    source VARCHAR(100),
    properties JSONB
);

CREATE TABLE IF NOT EXISTS alteration_zones (
    id SERIAL PRIMARY KEY,
    geom GEOMETRY(Polygon, 4326),
    zone_type VARCHAR(50),
    intensity DOUBLE PRECISION,
    area_m2 DOUBLE PRECISION,
    properties JSONB
);

CREATE TABLE IF NOT EXISTS change_areas (
    id SERIAL PRIMARY KEY,
    geom GEOMETRY(Polygon, 4326),
    change_type VARCHAR(50),
    magnitude DOUBLE PRECISION,
    date_before DATE,
    date_after DATE,
    properties JSONB
);

CREATE INDEX IF NOT EXISTS idx_sample_points_geom ON sample_points USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_lineaments_geom ON lineaments USING GIST(geom);
CREATE INDEX IF NOT EXISTS idx_alteration_zones_geom ON alteration_zones USING GIST(geom);
"""


class SpatialQueryEngine:
    """
    PostGIS-backed spatial query engine for AfriMine.

    Supports both PostGIS and in-memory fallback (GeoPandas/Shapely)
    when no database is available.
    """

    def __init__(self, config: PostGISConfig = None, use_postgis: bool = True):
        self.config = config or PostGISConfig()
        self.use_postgis = use_postgis
        self.engine = None
        self._in_memory_store = {
            "sample_points": [],
            "lineaments": [],
            "alteration_zones": [],
        }

        if use_postgis:
            self._connect()

    def _connect(self):
        """Connect to PostGIS database."""
        try:
            from sqlalchemy import create_engine
            self.engine = create_engine(self.config.connection_string)
            # Initialize tables
            with self.engine.connect() as conn:
                for stmt in INIT_SQL.split(";"):
                    stmt = stmt.strip()
                    if stmt:
                        conn.execute(stmt)
                conn.commit()
            logger.info("Connected to PostGIS")
        except Exception as e:
            logger.warning(f"PostGIS unavailable ({e}), using in-memory mode")
            self.use_postgis = False

    def insert_sample_point(self, name: str, lon: float, lat: float,
                            mineral_type: str = None,
                            collection_date: str = None,
                            properties: Dict = None) -> int:
        """
        Insert a geochemical sample point.

        Args:
            name: Sample identifier
            lon, lat: Coordinates (WGS84)
            mineral_type: Type of mineral found
            collection_date: Date string
            properties: Additional metadata

        Returns:
            Sample ID
        """
        if self.use_postgis and self.engine:
            sql = """
            INSERT INTO sample_points (name, geom, mineral_type, collection_date, properties)
            VALUES (%s, ST_SetSRID(ST_MakePoint(%s, %s), 4326), %s, %s, %s)
            RETURNING id;
            """
            with self.engine.connect() as conn:
                result = conn.execute(sql, (
                    name, lon, lat, mineral_type, collection_date,
                    str(properties or {})
                ))
                sample_id = result.fetchone()[0]
                conn.commit()
            logger.info(f"Inserted sample '{name}' (id={sample_id}) at ({lon}, {lat})")
            return sample_id
        else:
            self._in_memory_store["sample_points"].append({
                "id": len(self._in_memory_store["sample_points"]) + 1,
                "name": name, "lon": lon, "lat": lat,
                "mineral_type": mineral_type, "properties": properties,
            })
            return len(self._in_memory_store["sample_points"])

    def insert_lineament(self, x1: float, y1: float, x2: float, y2: float,
                         length: float, orientation: float,
                         source: str = "sentinel2") -> int:
        """Insert a detected lineament."""
        if self.use_postgis and self.engine:
            sql = """
            INSERT INTO lineaments (geom, length_m, orientation, source)
            VALUES (ST_SetSRID(ST_MakeLine(
                ST_MakePoint(%s, %s), ST_MakePoint(%s, %s)
            ), 4326), %s, %s, %s)
            RETURNING id;
            """
            with self.engine.connect() as conn:
                result = conn.execute(sql, (x1, y1, x2, y2, length, orientation, source))
                lid = result.fetchone()[0]
                conn.commit()
            return lid
        else:
            self._in_memory_store["lineaments"].append({
                "x1": x1, "y1": y1, "x2": x2, "y2": y2,
                "length": length, "orientation": orientation,
            })
            return len(self._in_memory_store["lineaments"])

    def samples_near_rivers(self, buffer_m: float = 500) -> List[Dict]:
        """
        Find samples within buffer_m meters of rivers/water bodies.

        Requires a 'waterways' table or uses NDWI-derived water features.
        """
        if self.use_postgis and self.engine:
            sql = """
            SELECT sp.id, sp.name, sp.mineral_type,
                   ST_X(sp.geom) as lon, ST_Y(sp.geom) as lat,
                   MIN(ST_Distance(sp.geom::geography, wl.geom::geography)) as dist_m
            FROM sample_points sp
            CROSS JOIN waterways wl
            WHERE ST_DWithin(sp.geom::geography, wl.geom::geography, %s)
            GROUP BY sp.id, sp.name, sp.mineral_type, sp.geom
            ORDER BY dist_m;
            """
            with self.engine.connect() as conn:
                result = conn.execute(sql, (buffer_m,))
                rows = [dict(row._mapping) for row in result]
            logger.info(f"Found {len(rows)} samples within {buffer_m}m of rivers")
            return rows
        else:
            logger.info("In-memory mode: river proximity requires waterway data")
            return []

    def samples_near_faults(self, buffer_m: float = 1000) -> List[Dict]:
        """
        Find samples within buffer_m meters of detected faults/lineaments.
        """
        if self.use_postgis and self.engine:
            sql = """
            SELECT sp.id, sp.name, sp.mineral_type,
                   ST_X(sp.geom) as lon, ST_Y(sp.geom) as lat,
                   MIN(ST_Distance(sp.geom::geography, l.geom::geography)) as dist_to_fault_m
            FROM sample_points sp
            CROSS JOIN lineaments l
            WHERE ST_DWithin(sp.geom::geography, l.geom::geography, %s)
            GROUP BY sp.id, sp.name, sp.mineral_type, sp.geom
            ORDER BY dist_to_fault_m;
            """
            with self.engine.connect() as conn:
                result = conn.execute(sql, (buffer_m,))
                rows = [dict(row._mapping) for row in result]
            logger.info(f"Found {len(rows)} samples within {buffer_m}m of faults")
            return rows
        else:
            # In-memory fallback using Shapely
            from shapely.geometry import Point, LineString
            from shapely.ops import transform as shapely_transform
            import pyproj

            points = self._in_memory_store["sample_points"]
            lines = self._in_memory_store["lineaments"]

            if not points or not lines:
                return []

            # Project to UTM for metric distances
            center_lon = np.mean([p["lon"] for p in points])
            utm_zone = int((center_lon + 180) / 6) + 1
            hemisphere = "north" if np.mean([p["lat"] for p in points]) >= 0 else "south"
            crs_wgs = pyproj.CRS("EPSG:4326")
            crs_utm = pyproj.CRS(f"+proj=utm +zone={utm_zone} +{hemisphere} +datum=WGS84")
            to_utm = pyproj.Transformer.from_crs(crs_wgs, crs_utm, always_xy=True).transform

            line_geoms = [
                shapely_transform(to_utm, LineString([(l["x1"], l["y1"]), (l["x2"], l["y2"])]))
                for l in lines
            ]

            results = []
            for p in points:
                pt = shapely_transform(to_utm, Point(p["lon"], p["lat"]))
                min_dist = min(pt.distance(line) for line in line_geoms)
                if min_dist <= buffer_m:
                    results.append({
                        "id": p["id"],
                        "name": p["name"],
                        "mineral_type": p.get("mineral_type"),
                        "lon": p["lon"],
                        "lat": p["lat"],
                        "dist_to_fault_m": min_dist,
                    })

            results.sort(key=lambda r: r["dist_to_fault_m"])
            logger.info(f"Found {len(results)} samples within {buffer_m}m of faults")
            return results

    def buffer_analysis(self, point: Tuple[float, float],
                        radii: List[float]) -> Dict[float, Dict]:
        """
        Multi-ring buffer analysis around a point.

        Args:
            point: (lon, lat) center
            radii: List of buffer radii in meters

        Returns:
            Dict mapping radius to feature counts within each ring
        """
        results = {}

        if self.use_postgis and self.engine:
            for radius in radii:
                sql = """
                SELECT
                    'sample_points' as layer,
                    COUNT(*) as count
                FROM sample_points
                WHERE ST_DWithin(
                    geom::geography,
                    ST_SetSRID(ST_MakePoint(%s, %s), 4326)::geography,
                    %s
                );
                """
                with self.engine.connect() as conn:
                    result = conn.execute(sql, (point[0], point[1], radius))
                    row = result.fetchone()
                    results[radius] = {"samples": row[0] if row else 0}
        else:
            from shapely.geometry import Point
            center = Point(point[0], point[1])
            for radius in radii:
                # Approximate degree buffer (rough)
                deg_buffer = radius / 111000
                buf = center.buffer(deg_buffer)
                count = sum(
                    1 for p in self._in_memory_store["sample_points"]
                    if buf.contains(Point(p["lon"], p["lat"]))
                )
                results[radius] = {"samples": count}

        logger.info(f"Buffer analysis: {results}")
        return results

    def spatial_join_alteration_samples(self) -> List[Dict]:
        """
        Join sample points with alteration zones to get
        alteration indices at each sample location.
        """
        if self.use_postgis and self.engine:
            sql = """
            SELECT sp.id, sp.name, sp.mineral_type,
                   az.zone_type, az.intensity,
                   ST_X(sp.geom) as lon, ST_Y(sp.geom) as lat
            FROM sample_points sp
            LEFT JOIN alteration_zones az
            ON ST_Within(sp.geom, az.geom)
            ORDER BY sp.id;
            """
            with self.engine.connect() as conn:
                result = conn.execute(sql)
                return [dict(row._mapping) for row in result]
        return []

    def export_geojson(self, table: str, output_path: str = None) -> str:
        """Export a table to GeoJSON."""
        import json

        if self.use_postgis and self.engine:
            sql = f"""
            SELECT json_build_object(
                'type', 'FeatureCollection',
                'features', json_agg(
                    json_build_object(
                        'type', 'Feature',
                        'geometry', ST_AsGeoJSON(geom)::json,
                        'properties', to_jsonb(t) - 'geom'
                    )
                )
            )
            FROM {table} t;
            """
            with self.engine.connect() as conn:
                result = conn.execute(sql)
                geojson = result.fetchone()[0]
        else:
            # In-memory export
            features = []
            for item in self._in_memory_store.get(table, []):
                if "lon" in item:
                    geom = {"type": "Point", "coordinates": [item["lon"], item["lat"]]}
                else:
                    continue
                props = {k: v for k, v in item.items() if k not in ("lon", "lat")}
                features.append({"type": "Feature", "geometry": geom, "properties": props})
            geojson = {"type": "FeatureCollection", "features": features}

        output_path = output_path or str(OUTPUT_DIR / f"{table}.geojson")
        with open(output_path, "w") as f:
            json.dump(geojson, f, indent=2, default=str)

        logger.info(f"Exported {table} to {output_path}")
        return output_path
