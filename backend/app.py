from pathlib import Path
from functools import lru_cache
import gzip
import json
import re
import subprocess

from flask import Flask, Response, abort, request
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ROOT = Path(__file__).resolve().parents[1]
PMTILES_BIN = ROOT / "tools" / "pmtiles" / "pmtiles.exe"
PMTILES_DIR = Path(__file__).resolve().parent / "pmtiles"
GEOJSON_DIR = Path(__file__).resolve().parent / "geojson"
PROPERTY_PATTERN = re.compile(r'"properties"\s*:\s*(\{[^{}]*\})')

DATASETS = {
	"county": PMTILES_DIR / "county.pmtiles",
	"township": PMTILES_DIR / "township.pmtiles",
	"village": PMTILES_DIR / "village.pmtiles",
}


@app.get("/health")
def health():
	return {"ok": True}


def _read_geojson_properties(file_name):
	path = GEOJSON_DIR / file_name
	if not path.exists():
		return []

	content = path.read_text(encoding="utf-8", errors="ignore")
	rows = []
	for match in PROPERTY_PATTERN.finditer(content):
		try:
			rows.append(json.loads(match.group(1)))
		except json.JSONDecodeError:
			continue
	return rows


def _read_geojson(file_name):
	path = GEOJSON_DIR / file_name
	if not path.exists():
		return {"type": "FeatureCollection", "features": []}

	return json.loads(path.read_text(encoding="utf-8", errors="ignore"))


def _split_codes(value):
	if not value:
		return []
	if isinstance(value, str):
		return [code.strip() for code in value.split(",") if code.strip()]
	if isinstance(value, list):
		return [str(code).strip() for code in value if str(code).strip()]
	return []


@lru_cache(maxsize=1)
def _build_region_feature_indexes():
	county_features = _read_geojson("county.geojson").get("features", [])
	township_features = _read_geojson("township.geojson").get("features", [])
	village_features = _read_geojson("village.geojson").get("features", [])

	def index_by_property(features, property_name):
		index = {}
		for feature in features:
			code = feature.get("properties", {}).get(property_name, "")
			if code:
				index[code] = feature
		return index

	return {
		"county": index_by_property(county_features, "COUNTYCODE"),
		"township": index_by_property(township_features, "TOWNCODE"),
		"village": index_by_property(village_features, "VILLCODE"),
	}


@lru_cache(maxsize=1)
def _build_regions_tree():
	county_rows = _read_geojson_properties("county.geojson")
	township_rows = _read_geojson_properties("township.geojson")
	village_rows = _read_geojson_properties("village.geojson")

	counties_by_code = {}
	counties = []

	def ensure_county(county_code, county_id="", county_name="", county_eng=""):
		code = county_code or "__unknown__"
		existing = counties_by_code.get(code)
		if existing:
			if county_id and not existing["countyId"]:
				existing["countyId"] = county_id
			if county_name and not existing["countyName"]:
				existing["countyName"] = county_name
			if county_eng and not existing["countyEng"]:
				existing["countyEng"] = county_eng
			return existing

		created = {
			"countyId": county_id or "",
			"countyCode": county_code or "",
			"countyName": county_name or "",
			"countyEng": county_eng or "",
			"townships": []
		}
		counties_by_code[code] = created
		counties.append(created)
		return created

	for row in county_rows:
		ensure_county(
			row.get("COUNTYCODE", ""),
			row.get("COUNTYID", ""),
			row.get("COUNTYNAME", ""),
			row.get("COUNTYENG", ""),
		)

	townships_by_code = {}
	for row in township_rows:
		county = ensure_county(
			row.get("COUNTYCODE", ""),
			row.get("COUNTYID", ""),
			row.get("COUNTYNAME", ""),
		)

		town_code = row.get("TOWNCODE", "")
		key = town_code or f"__unknown_town__::{row.get('TOWNID', '')}::{len(townships_by_code)}"
		township = townships_by_code.get(key)
		if township:
			continue

		township = {
			"townId": row.get("TOWNID", ""),
			"townCode": town_code,
			"townName": row.get("TOWNNAME", ""),
			"townEng": row.get("TOWNENG", ""),
			"villages": []
		}
		townships_by_code[key] = township
		county["townships"].append(township)

	for row in village_rows:
		county = ensure_county(
			row.get("COUNTYCODE", ""),
			row.get("COUNTYID", ""),
			row.get("COUNTYNAME", ""),
		)

		town_code = row.get("TOWNCODE", "")
		town_key = town_code or f"__unknown_town_for_village__::{row.get('TOWNID', '')}"
		township = townships_by_code.get(town_key)
		if not township:
			township = {
				"townId": row.get("TOWNID", ""),
				"townCode": town_code,
				"townName": row.get("TOWNNAME", ""),
				"townEng": "",
				"villages": []
			}
			townships_by_code[town_key] = township
			county["townships"].append(township)

		village_code = row.get("VILLCODE", "")
		village = {
			"villageCode": village_code,
			"villageName": row.get("VILLNAME", ""),
			"villageEng": row.get("VILLENG", ""),
		}
		township["villages"].append(village)

	for county in counties:
		county["townships"].sort(key=lambda item: (item["townCode"], item["townName"]))
		for township in county["townships"]:
			township["villages"].sort(key=lambda item: (item["villageCode"], item["villageName"]))

	counties.sort(key=lambda item: item["countyId"])

	total_townships = sum(len(county["townships"]) for county in counties)
	total_villages = sum(len(township["villages"]) for county in counties for township in county["townships"])

	return {
		"counties": counties,
		"summary": {
			"countyCount": len(counties),
			"townshipCount": total_townships,
			"villageCount": total_villages,
		}
	}


def _make_range_node(node_id, name, description, color, level, code, children=None, metadata=None):
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


@lru_cache(maxsize=1)
def _build_ranges_tree():
	regions = _build_regions_tree()
	ranges = []

	for county in regions["counties"]:
		township_nodes = []

		for town in county.get("townships", []):
			village_nodes = [
				_make_range_node(
					f"village-{village.get('villageCode', '')}",
					village.get("villageName", ""),
					village.get("villageEng", ""),
					"#d17827",
					"village",
					village.get("villageCode", ""),
					metadata={"sourceProperty": "VILLCODE"},
				)
				for village in town.get("villages", [])
				if village.get("villageCode")
			]

			if not town.get("townCode"):
				continue

			township_nodes.append(
				_make_range_node(
					f"township-{town.get('townCode', '')}",
					town.get("townName", ""),
					town.get("townEng", ""),
					"#27a693",
					"township",
					town.get("townCode", ""),
					children=village_nodes,
					metadata={"sourceProperty": "TOWNCODE"},
				)
			)

		if not county.get("countyCode"):
			continue

		ranges.append(
			_make_range_node(
				f"county-{county.get('countyCode', '')}",
				county.get("countyName", ""),
				county.get("countyEng", ""),
				"#7fb3ff",
				"county",
				county.get("countyCode", ""),
				children=township_nodes,
				metadata={"sourceProperty": "COUNTYCODE"},
			)
		)

	return {
		"ranges": ranges,
		"summary": regions["summary"],
	}


@app.get("/ranges/tree")
def ranges_tree():
	return _build_ranges_tree()


@app.route("/regions/range-geojson", methods=["GET", "POST"])
def range_geojson():
	if request.method == "POST":
		payload = request.get_json(silent=True) or {}
		county_codes = _split_codes(payload.get("countyCodes"))
		town_codes = _split_codes(payload.get("townCodes"))
		village_codes = _split_codes(payload.get("villageCodes"))
	else:
		county_codes = _split_codes(request.args.get("countyCodes"))
		town_codes = _split_codes(request.args.get("townCodes"))
		village_codes = _split_codes(request.args.get("villageCodes"))

	indexes = _build_region_feature_indexes()
	features = []
	seen = set()
	range_styles = {
		"county": "#7fb3ff",
		"township": "#57a6f5",
		"village": "#d17827",
	}

	for dataset, codes in (
		("county", county_codes),
		("township", town_codes),
		("village", village_codes),
	):
		for code in codes:
			feature = indexes[dataset].get(code)
			if not feature:
				continue
			key = f"{dataset}:{code}"
			if key in seen:
				continue
			seen.add(key)
			features.append({
				**feature,
				"properties": {
					**feature.get("properties", {}),
					"rangeId": key,
					"rangeColor": range_styles.get(dataset, "#57a6f5"),
					"rangeType": "admin",
					"rangeLevel": dataset,
				}
			})

	return {
		"type": "FeatureCollection",
		"features": features,
	}


@app.get("/tiles/<dataset>/<int:z>/<int:x>/<int:y>.pbf")
def tile(dataset, z, x, y):
	pmtiles_path = DATASETS.get(dataset)
	if not pmtiles_path or not pmtiles_path.exists():
		return Response(status=404)

	if not PMTILES_BIN.exists():
		abort(500, description="pmtiles.exe not found")

	result = subprocess.run(
		[str(PMTILES_BIN), "tile", str(pmtiles_path), str(z), str(x), str(y)],
		capture_output=True,
		check=False,
	)

	if result.returncode != 0 or not result.stdout:
		return Response(status=404)

	payload = result.stdout
	if payload.startswith(b"\x1f\x8b"):
		try:
			payload = gzip.decompress(payload)
		except OSError:
			return Response(status=404)

	if not payload:
		return Response(status=404)

	if payload[0] not in (0x1A, 0x0A):
		return Response(status=404)

	headers = {"Content-Type": "application/vnd.mapbox-vector-tile"}
	return Response(payload, headers=headers)


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000, debug=True)
