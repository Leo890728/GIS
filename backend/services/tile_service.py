import gzip
import subprocess


def read_vector_tile(pmtiles_bin, datasets, dataset, z, x, y):
    pmtiles_path = datasets.get(dataset)
    if not pmtiles_path or not pmtiles_path.exists():
        return None

    if not pmtiles_bin.exists():
        raise FileNotFoundError("pmtiles.exe not found")

    result = subprocess.run(
        [str(pmtiles_bin), "tile", str(pmtiles_path), str(z), str(x), str(y)],
        capture_output=True,
        check=False,
    )

    if result.returncode != 0 or not result.stdout:
        return None

    payload = result.stdout
    if payload.startswith(b"\x1f\x8b"):
        try:
            payload = gzip.decompress(payload)
        except OSError:
            return None

    if not payload:
        return None

    if payload[0] not in (0x1A, 0x0A):
        return None

    return payload
