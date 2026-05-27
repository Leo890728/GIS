import tempfile
import unittest
from pathlib import Path
from unittest import mock

from backend.config import GEOJSON_DIR, RANGE_STYLES
from backend.services.regions_db import RegionsSyncError
from backend.services.regions_service import RegionsService


class RegionsSyncModeTestCase(unittest.TestCase):
    def test_manual_mode_requires_ready_db(self):
        with tempfile.TemporaryDirectory() as temp_dir:
            db_path = Path(temp_dir) / "regions.sqlite"
            with self.assertRaises(RegionsSyncError):
                RegionsService(
                    geojson_dir=GEOJSON_DIR,
                    range_styles=RANGE_STYLES,
                    db_path=db_path,
                    spatialite_extension_path=None,
                    sync_mode="manual",
                    sync_strict=True,
                )

    def test_startup_mode_triggers_import_when_sync_required(self):
        with mock.patch("backend.services.regions_service.is_sync_required", return_value=True) as sync_required:
            with mock.patch("backend.services.regions_service.import_admin_regions") as importer:
                with mock.patch("backend.services.regions_service.validate_regions_db_ready") as validate:
                    RegionsService(
                        geojson_dir=GEOJSON_DIR,
                        range_styles=RANGE_STYLES,
                        db_path=Path("dummy.sqlite"),
                        spatialite_extension_path="dummy.dll",
                        sync_mode="startup",
                        sync_strict=True,
                    )

                    sync_required.assert_called_once()
                    importer.assert_called_once()
                    validate.assert_called_once()

    def test_startup_mode_skips_import_when_sync_not_required(self):
        with mock.patch("backend.services.regions_service.is_sync_required", return_value=False) as sync_required:
            with mock.patch("backend.services.regions_service.import_admin_regions") as importer:
                with mock.patch("backend.services.regions_service.validate_regions_db_ready") as validate:
                    RegionsService(
                        geojson_dir=GEOJSON_DIR,
                        range_styles=RANGE_STYLES,
                        db_path=Path("dummy.sqlite"),
                        spatialite_extension_path="dummy.dll",
                        sync_mode="startup",
                        sync_strict=True,
                    )

                    sync_required.assert_called_once()
                    importer.assert_not_called()
                    validate.assert_called_once()

    def test_startup_non_strict_tolerates_sync_failure_with_existing_db(self):
        with mock.patch("backend.services.regions_service.is_sync_required", return_value=True):
            with mock.patch(
                "backend.services.regions_service.import_admin_regions",
                side_effect=RegionsSyncError("sync failed"),
            ):
                with mock.patch("backend.services.regions_service.validate_regions_db_ready") as validate:
                    RegionsService(
                        geojson_dir=GEOJSON_DIR,
                        range_styles=RANGE_STYLES,
                        db_path=Path("dummy.sqlite"),
                        spatialite_extension_path="dummy.dll",
                        sync_mode="startup",
                        sync_strict=False,
                    )
                    validate.assert_called_once()

    def test_startup_non_strict_still_raises_when_db_not_ready(self):
        with mock.patch("backend.services.regions_service.is_sync_required", return_value=True):
            with mock.patch(
                "backend.services.regions_service.import_admin_regions",
                side_effect=RegionsSyncError("sync failed"),
            ):
                with mock.patch(
                    "backend.services.regions_service.validate_regions_db_ready",
                    side_effect=RegionsSyncError("db not ready"),
                ):
                    with self.assertRaises(RegionsSyncError):
                        RegionsService(
                            geojson_dir=GEOJSON_DIR,
                            range_styles=RANGE_STYLES,
                            db_path=Path("dummy.sqlite"),
                            spatialite_extension_path="dummy.dll",
                            sync_mode="startup",
                            sync_strict=False,
                        )


if __name__ == "__main__":
    unittest.main()
