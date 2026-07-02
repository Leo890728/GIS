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


def assemble_regions_tree(county_rows, township_rows, village_rows):
    """Stitch county/township/village rows into the nested regions tree."""
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
        township["villages"].append({
            "villageCode": row["villcode"] or "",
            "villageName": row["villname"] or "",
            "villageEng": row["villeng"] or "",
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
                        metadata={"sourceProperty": "VILLCODE"},
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


def regions_tree_to_stat_ranges(regions, sz2_count_by_town):
    """Transform the regions tree into the statistical-area tree roots.

    縣市/鄉鎮節點沿用行政區資料，但 id 加上 ``stat-`` 前綴以免與行政區樹
    的節點互相干擾；鄉鎮以下（二級發布區→一級發布區→最小統計區）數量龐大，
    只放 lazy-load 標記（metadata.childLevel / childCount），由前端展開時再載入。
    """
    ranges = []

    for county in regions["counties"]:
        township_nodes = []
        for town in county.get("townships", []):
            tcode = town.get("townCode", "")
            if not tcode:
                continue
            township_nodes.append(
                make_range_node(
                    f"stat-township-{tcode}",
                    town.get("townName", ""),
                    town.get("townEng", ""),
                    "#27a693",
                    "township",
                    tcode,
                    metadata={
                        "sourceProperty": "TOWNCODE",
                        "childLevel": "stat_zone_2",
                        "childCount": int(sz2_count_by_town.get(tcode, 0)),
                    },
                )
            )

        if not county.get("countyCode"):
            continue
        ranges.append(
            make_range_node(
                f"stat-county-{county['countyCode']}",
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


def stat_zone2_rows_to_range_nodes(rows, color, sz1_count_by_code2):
    """Turn stat_zone_2 rows into lazy 二級發布區 range nodes."""
    return [
        make_range_node(
            f"stat_zone_2-{row['code2']}",
            row["code2"],
            "",
            color,
            "stat_zone_2",
            row["code2"],
            metadata={
                "sourceProperty": "CODE2",
                "childLevel": "stat_zone_1",
                "childCount": int(sz1_count_by_code2.get(row["code2"], 0)),
            },
        )
        for row in rows
    ]


def stat_zone1_rows_to_range_nodes(rows, color, sz_count_by_code1):
    """Turn stat_zone_1 rows into lazy 一級發布區 range nodes."""
    return [
        make_range_node(
            f"stat_zone_1-{row['code1']}",
            row["code1"],
            "",
            color,
            "stat_zone_1",
            row["code1"],
            metadata={
                "sourceProperty": "CODE1",
                "childLevel": "stat_zone",
                "childCount": int(sz_count_by_code1.get(row["code1"], 0)),
            },
        )
        for row in rows
    ]


def stat_zone_rows_to_range_nodes(rows, color, parent_metadata=None):
    """Turn stat-zone rows (codebase + p_cnt) into selectable leaf range nodes."""
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
                    "pCnt": population,
                    **(parent_metadata or {}),
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
