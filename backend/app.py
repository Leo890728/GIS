from pathlib import Path
import gzip
import subprocess

from flask import Flask, Response, abort
from flask_cors import CORS

app = Flask(__name__)
CORS(app)

ROOT = Path(__file__).resolve().parents[1]
PMTILES_BIN = ROOT / "tools" / "pmtiles" / "pmtiles.exe"
PMTILES_DIR = Path(__file__).resolve().parent / "pmtiles"

DATASETS = {
	"county": PMTILES_DIR / "county.pmtiles",
	"township": PMTILES_DIR / "township.pmtiles",
	"village": PMTILES_DIR / "village.pmtiles",
}


@app.get("/health")
def health():
	return {"ok": True}


@app.get("/tiles/<dataset>/<int:z>/<int:x>/<int:y>.pbf")
def tile(dataset, z, x, y):
	pmtiles_path = DATASETS.get(dataset)
	if not pmtiles_path or not pmtiles_path.exists():
		return Response(status=204)

	if not PMTILES_BIN.exists():
		abort(500, description="pmtiles.exe not found")

	result = subprocess.run(
		[str(PMTILES_BIN), "tile", str(pmtiles_path), str(z), str(x), str(y)],
		capture_output=True,
		check=False,
	)

	if result.returncode != 0 or not result.stdout:
		return Response(status=204)

	payload = result.stdout
	if payload.startswith(b"\x1f\x8b"):
		try:
			payload = gzip.decompress(payload)
		except OSError:
			return Response(status=204)

	if not payload:
		return Response(status=204)

	if payload[0] not in (0x1A, 0x0A):
		return Response(status=204)

	headers = {"Content-Type": "application/vnd.mapbox-vector-tile"}
	return Response(payload, headers=headers)


if __name__ == "__main__":
	app.run(host="0.0.0.0", port=5000, debug=True)
