"""
Tests for Viewtron Python SDK event classes.

Uses XML fixture files from the IP-Camera-API repo's examples/ directory.
These fixtures have placeholder strings instead of real base64 image data.
"""

import os
import pytest

from viewtron import (
    # IPC v1.x
    LPR,
    FaceDetection,
    IntrusionDetection,
    IntrusionEntry,
    IntrusionExit,
    VideoMetadata,
    # NVR v2.0
    VehicleLPR,
    FaceDetectionV2,
    RegionIntrusion,
    LineCrossing,
    TargetCountingByLine,
    TargetCountingByArea,
    VideoMetadataV2,
)

# Path to XML fixtures in the API repo
FIXTURES_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "IP-Camera-API", "examples"
)
IPC_DIR = os.path.join(FIXTURES_DIR, "ipc-v1x")
NVR_DIR = os.path.join(FIXTURES_DIR, "nvr-v2")


def load_fixture(subdir, filename):
    path = os.path.join(FIXTURES_DIR, subdir, filename)
    with open(path, "r") as f:
        return f.read()


# ====================== IPC v1.x ======================


class TestLPR:
    @pytest.fixture
    def event(self):
        return LPR(load_fixture("ipc-v1x", "lpr.xml"))

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "VEHICE"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "License Plate Detection"

    def test_plate_number(self, event):
        assert event.get_plate_number() == "ABC1234"

    def test_plate_group(self, event):
        assert event.get_plate_group() == "whiteList"

    def test_timestamp(self, event):
        ts = event.get_time_stamp_formatted()
        assert ts  # non-empty
        assert "1970" not in ts  # not epoch zero

    def test_images_placeholder(self, event):
        # Fixtures have placeholder text, not real base64
        # source_image_exists checks length > 0 AND content is truthy
        # The placeholder "BASE64_JPEG..." will be truthy but not valid base64
        assert isinstance(event.source_image_exists(), bool)
        assert isinstance(event.target_image_exists(), bool)


class TestFaceDetection:
    @pytest.fixture
    def event(self):
        return FaceDetection(load_fixture("ipc-v1x", "face-detection.xml"))

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "VFD"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Face Detection"

    def test_timestamp(self, event):
        ts = event.get_time_stamp_formatted()
        assert ts
        assert "1970" not in ts


class TestIntrusionDetection:
    @pytest.fixture
    def event(self):
        return IntrusionDetection(
            load_fixture("ipc-v1x", "perimeter-intrusion.xml")
        )

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "PEA"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Line Crossing / Intrusion"

    def test_timestamp(self, event):
        ts = event.get_time_stamp_formatted()
        assert ts
        assert "1970" not in ts


class TestIntrusionLineCrossing:
    """PEA with tripwire block instead of perimeter block."""

    @pytest.fixture
    def event(self):
        return IntrusionDetection(
            load_fixture("ipc-v1x", "line-crossing.xml")
        )

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "PEA"

    def test_constructs_without_error(self, event):
        assert event is not None


class TestIntrusionEntry:
    @pytest.fixture
    def event(self):
        return IntrusionEntry(load_fixture("ipc-v1x", "zone-entry.xml"))

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "AOIENTRY"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Intrusion Zone Entry"


class TestIntrusionExit:
    @pytest.fixture
    def event(self):
        # zone-exit.xml should be same structure as zone-entry with AOILEAVE
        return IntrusionExit(load_fixture("ipc-v1x", "zone-exit.xml"))

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "AOILEAVE"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Intrusion Zone Exit"


class TestVideoMetadata:
    @pytest.fixture
    def event(self):
        return VideoMetadata(load_fixture("ipc-v1x", "video-metadata.xml"))

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "VSD"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Video Metadata"


# ====================== NVR v2.0 ======================


class TestVehicleLPR:
    @pytest.fixture
    def event(self):
        return VehicleLPR(load_fixture("nvr-v2", "vehicle-lpr.xml"))

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "vehicle"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "License Plate Detection"

    def test_plate_number(self, event):
        assert event.get_plate_number() == "JP116D"

    def test_car_brand(self, event):
        assert event.get_car_brand() == "GMC"

    def test_car_model(self, event):
        assert event.get_car_model() == "GMC_SAVANA"

    def test_car_type(self, event):
        assert event.get_car_type() == "mpv"

    def test_car_color(self, event):
        assert event.get_car_color() == "white"

    def test_plate_color(self, event):
        assert event.get_plate_color() == "white"

    def test_device_ip(self, event):
        assert event.device_ip == "192.168.0.60"

    def test_channel_id(self, event):
        assert event.get_channel_id() == "2"

    def test_ip_cam(self, event):
        assert event.get_ip_cam() == "Device Name"


class TestFaceDetectionV2:
    @pytest.fixture
    def event(self):
        return FaceDetectionV2(load_fixture("nvr-v2", "face-detection.xml"))

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "videoFaceDetect"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Face Detection"

    def test_face_age(self, event):
        assert event.get_face_age() == "middleAged"

    def test_face_sex(self, event):
        assert event.get_face_sex() == "male"

    def test_face_glasses(self, event):
        assert event.get_face_glasses() == "unknown"

    def test_face_mask(self, event):
        assert event.get_face_mask() == "unknown"

    def test_device_ip(self, event):
        assert event.device_ip == "192.168.0.50"

    def test_ip_cam(self, event):
        assert event.get_ip_cam() == "Office"


class TestRegionIntrusion:
    @pytest.fixture
    def event(self):
        return RegionIntrusion(
            load_fixture("nvr-v2", "region-intrusion.xml")
        )

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "regionIntrusion"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Perimeter Intrusion"

    def test_device_ip(self, event):
        assert event.device_ip == "192.168.0.60"


class TestLineCrossing:
    @pytest.fixture
    def event(self):
        return LineCrossing(load_fixture("nvr-v2", "line-crossing.xml"))

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "lineCrossing"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Line Crossing"


class TestTargetCountingByLine:
    @pytest.fixture
    def event(self):
        return TargetCountingByLine(
            load_fixture("nvr-v2", "target-counting-by-line.xml")
        )

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "targetCountingByLine"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Target Counting by Line"


class TestTargetCountingByArea:
    @pytest.fixture
    def event(self):
        return TargetCountingByArea(
            load_fixture("nvr-v2", "target-counting-by-area.xml")
        )

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "targetCountingByArea"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Target Counting by Area"


class TestVideoMetadataV2:
    @pytest.fixture
    def event(self):
        return VideoMetadataV2(
            load_fixture("nvr-v2", "video-metadata.xml")
        )

    def test_alarm_type(self, event):
        assert event.get_alarm_type() == "videoMetadata"

    def test_alarm_description(self, event):
        assert event.get_alarm_description() == "Video Metadata"

    def test_device_ip(self, event):
        assert event.device_ip == "192.168.0.60"


# ====================== Context Manager ======================


class TestViewtronCamera:
    def test_context_manager(self):
        from viewtron import ViewtronCamera

        with ViewtronCamera("192.168.0.1", "admin", "pass") as cam:
            assert cam.host == "192.168.0.1"
            assert cam.username == "admin"

    def test_repr(self):
        from viewtron import ViewtronCamera

        cam = ViewtronCamera("192.168.0.1", "admin", "pass")
        assert repr(cam) == "ViewtronCamera(192.168.0.1)"

    def test_base_url_default_port(self):
        from viewtron import ViewtronCamera

        cam = ViewtronCamera("192.168.0.1", "admin", "pass")
        assert cam.base_url == "http://192.168.0.1"

    def test_base_url_custom_port(self):
        from viewtron import ViewtronCamera

        cam = ViewtronCamera("192.168.0.1", "admin", "pass", port=8080)
        assert cam.base_url == "http://192.168.0.1:8080"


# ====================== ViewtronEvent Factory ======================


class TestViewtronEvent:
    def test_lpr_ipc(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("ipc-v1x", "lpr.xml"))
        assert event is not None
        assert event.category == "lpr"
        assert event.get_alarm_type() == "VEHICE"
        assert event.get_plate_number() == "ABC1234"
        assert event.get_plate_group() == "whiteList"

    def test_lpr_nvr(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "vehicle-lpr.xml"))
        assert event is not None
        assert event.category == "lpr"
        assert event.get_alarm_type() == "vehicle"
        assert event.get_plate_number() == "JP116D"
        assert event.get_car_brand() == "GMC"

    def test_intrusion_ipc(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("ipc-v1x", "perimeter-intrusion.xml"))
        assert event is not None
        assert event.category == "intrusion"
        assert event.get_alarm_type() == "PEA"

    def test_intrusion_nvr(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "region-intrusion.xml"))
        assert event is not None
        assert event.category == "intrusion"
        assert event.get_alarm_type() == "regionIntrusion"

    def test_face_ipc(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("ipc-v1x", "face-detection.xml"))
        assert event is not None
        assert event.category == "face"
        assert event.get_alarm_type() == "VFD"

    def test_face_nvr(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "face-detection.xml"))
        assert event is not None
        assert event.category == "face"
        assert event.get_face_age() == "middleAged"
        assert event.get_face_sex() == "male"

    def test_line_crossing_nvr(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "line-crossing.xml"))
        assert event is not None
        assert event.category == "intrusion"

    def test_counting_by_line_nvr(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "target-counting-by-line.xml"))
        assert event is not None
        assert event.category == "counting"

    def test_counting_by_area_nvr(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "target-counting-by-area.xml"))
        assert event is not None
        assert event.category == "counting"

    def test_video_metadata_ipc(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("ipc-v1x", "video-metadata.xml"))
        assert event is not None
        assert event.category == "metadata"

    def test_video_metadata_nvr(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "video-metadata.xml"))
        assert event is not None
        assert event.category == "metadata"

    def test_zone_entry(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("ipc-v1x", "zone-entry.xml"))
        assert event is not None
        assert event.category == "intrusion"

    def test_zone_exit(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("ipc-v1x", "zone-exit.xml"))
        assert event is not None
        assert event.category == "intrusion"

    def test_keepalive_ipc_returns_none(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("ipc-v1x", "keepalive.xml"))
        assert event is None

    def test_keepalive_nvr_returns_none(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "keepalive.xml"))
        assert event is None

    def test_alarm_status_ipc_returns_none(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("ipc-v1x", "alarm-status.xml"))
        assert event is None

    def test_alarm_status_nvr_returns_none(self):
        from viewtron import ViewtronEvent

        event = ViewtronEvent(load_fixture("nvr-v2", "alarm-status.xml"))
        assert event is None

    def test_empty_body_returns_none(self):
        from viewtron import ViewtronEvent

        assert ViewtronEvent("") is None
        assert ViewtronEvent(None) is None

    def test_non_xml_returns_none(self):
        from viewtron import ViewtronEvent

        assert ViewtronEvent("not xml at all") is None
