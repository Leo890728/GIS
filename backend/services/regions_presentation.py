"""Pure presentation builders for regions/ranges data.

These turn already-fetched DB rows (sqlite3.Row or any mapping that supports
``row[key]`` and ``row.keys()``) into the domain trees, range nodes, and GeoJSON
features returned by :class:`backend.services.regions_service.RegionsService`.
Keeping them free of DB access makes them deterministic and unit-testable.
"""

import json


def make_range_node(node_id, name, description, color, level, code, children=None, metadata=None):
    return {
        "id": node_id,
        "name": name or code or node_id,
        "description": description or "",
        "color": color,
        "type": "admin",
        "level": level,
        "code": code or "",
        "selectable": True,
        "metadata": metadata or {},
        "children": children or [],
    }


def assemble_regions_tree(county_rows, township_rows, village_rows, sz_count_rows):
    """Stitch county/township/village rows into the nested regions tree."""
    sz_count = {row["villcode"]: row["cnt"] for row in sz_count_rows}

    counties_by_code = {}
    counties = []
    for row in county_rows:
        county = {
            "countyId": row["countyid"] or "",
            "countyCode": row["countycode"] or "",
            "countyName": row["countyname"] or "",
            "countyEng": row["countyeng"] or "",
            "townships": [],
        }
        counties_by_code[row["countycode"]] = county
        counties.append(county)

    townships_by_code = {}
    for row in township_rows:
        county = counties_by_code.get(row["countycode"])
        if not county:
            continue
        township = {
            "townId": row["townid"] or "",
            "townCode": row["towncode"] or "",
            "townName": row["townname"] or "",
            "townEng": row["towneng"] or "",
            "villages": [],
        }
        townships_by_code[row["towncode"]] = township
        county["townships"].append(township)

    for row in village_rows:
        township = townships_by_code.get(row["towncode"])
        if not township:
            continue
        vcode = row["villcode"] or ""
        township["villages"].append({
            "villageCode": vcode,
            "villageName": row["villname"] or "",
            "villageEng": row["villeng"] or "",
            "statZoneCount": sz_count.get(vcode, 0),
        })

    total_townships = sum(len(c["townships"]) for c in counties)
    total_villages = sum(len(t["villages"]) for c in counties for t in c["townships"])

    return {
        "counties": counties,
        "summary": {
            "countyCount": len(counties),
            "townshipCount": total_townships,
            "villageCount": total_villages,
        },
    }


def regions_tree_to_ranges(regions):
    """Transform the regions tree into selectable county/township/village nodes."""
    ranges = []

    for county in regions["counties"]:
        township_nodes = []
        for town in county.get("townships", []):
            village_nodes = []
            for village in town.get("villages", []):
                vcode = village.get("villageCode", "")
                if not vcode:
                    continue
                village_nodes.append(
                    make_range_node(
                        f"village-{vcode}",
                        village.get("villageName", ""),
                        village.get("villageEng", ""),
                        "#d17827",
                        "village",
                        vcode,
                        metadata={
                            "sourceProperty": "VILLCODE",
                            "statZoneCount": int(village.get("statZoneCount", 0)),
                        },
                    )
                )

            if not town.get("townCode"):
                continue
            township_nodes.append(
                make_range_node(
                    f"township-{town['townCode']}",
                    town.get("townName", ""),
                    town.get("townEng", ""),
                    "#27a693",
                    "township",
                    town["townCode"],
                    children=village_nodes,
                    metadata={"sourceProperty": "TOWNCODE"},
                )
            )

        if not county.get("countyCode"):
            continue
        ranges.append(
            make_range_node(
                f"county-{county['countyCode']}",
                county.get("countyName", ""),
                county.get("countyEng", ""),
                "#7fb3ff",
                "county",
                county["countyCode"],
                children=township_nodes,
                metadata={"sourceProperty": "COUNTYCODE"},
            )
        )

    return {"ranges": ranges, "summary": regions["summary"]}


def stat_zone_rows_to_range_nodes(rows, color, village_code):
    """Turn stat_zone_point_cache rows into selectable stat-zone range nodes."""
    ranges = []
    for row in rows:
        codebase = row["codebase"]
        population = row["p_cnt"]
        pop_text = ""
        if population is not None:
            try:
                pop_text = f"Population {int(float(population)):,}"
            except (TypeError, ValueError):
                pass
        ranges.append(
            make_range_node(
                f"stat_zone-{codebase}",
                codebase,
                pop_text,
                color,
                "stat_zone",
                codebase,
                metadata={
                    "sourceProperty": "CODEBASE",
                    "parentVillageCode": village_code,
                    "pCnt": population,
                },
            )
        )
    return ranges


def range_feature_from_row(row, layer, code_col, color):
    """Build one range GeoJSON Feature from a SpatiaLite row, or None if no geometry."""
    geom_json = row["_geom"]
    if not geom_json:
        return None
    key = f"{layer}:{row[code_col]}"
    props = {k: row[k] for k in row.keys() if k not in ("GEOMETRY", "_geom")}
    props.update({
        "rangeId": key,
        "rangeColor": color,
        "rangeType": "admin",
        "rangeLevel": layer,
    })
    return {
        "type": "Feature",
        "geometry": json.loads(geom_json),
        "properties": props,
    }


def stat_zone_point_feature_from_row(row):
    """Build one stat-zone population point Feature from a cache row."""
    return {
        "type": "Feature",
        "id": row["codebase"],
        "geometry": {"type": "Point", "coordinates": [row["lng"], row["lat"]]},
        "properties": {
            "CODEBASE": row["codebase"],
            "VILLAGE_CODE": row["villcode"],
            "COUNTY_CODE": row["county_id"],
            "TOWN_CODE": row["town_id"],
            "P_CNT": row["p_cnt"],
            "X": row["lng"],
            "Y": row["lat"],
        },
    }
