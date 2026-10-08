"""
Tests for Viewtron Python SDK event classes.

Uses XML fixture files from the IP-Camera-API repo's examples/ directory.
These fixtures have placeholder strings instead of real base64 image data.
"""

import os
import re
from datetime import datetime

import pytest

from viewtron import (
    ViewtronEvent,
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
from viewtron.events import _classify_post

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


LOCAL_FIXTURES = os.path.join(os.path.dirname(__file__), "fixtures")


def load_local(subdir, filename):
    path = os.path.join(LOCAL_FIXTURES, subdir, filename)
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


# ============================================================
# Empty image / text elements (GitHub issue #1)
# ============================================================

class TestEmptyElements:
    """xmltodict turns <x type="string"/> into {'@type': 'string'} (no '#text')
    and <x/> into None. Neither should crash parsing or produce a fake image."""

    AOI_EMPTY_SOURCE = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<config version="1.7" xmlns="http://www.ipc.com/ver10">'
        '<smartType type="openAlramObj">AOIENTRY</smartType>'
        '<sourceDataInfo><sourceBase64Length type="uint32">0</sourceBase64Length>'
        '<sourceBase64Data type="string"><![CDATA[]]></sourceBase64Data></sourceDataInfo>'
        '</config>'
    )

    AOI_EMPTY_TARGET = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        '<config version="1.7" xmlns="http://www.ipc.com/ver10">'
        '<smartType type="openAlramObj">AOIENTRY</smartType>'
        '<listInfo type="list" count="1"><item><targetImageData>'
        '<targetBase64Length type="uint32">10</targetBase64Length>'
        '<targetBase64Data type="string"></targetBase64Data>'
        '</targetImageData></item></listInfo>'
        '</config>'
    )

    def test_issue_repro_no_crash(self):
        from viewtron.events import CommonImagesLocation
        xml = ('<?xml version="1.0" encoding="UTF-8"?><config><sourceDataInfo>'
               '<sourceBase64Data type="jpg"/></sourceDataInfo></config>')
        event = CommonImagesLocation(xml)
        assert event.source_image_exists() is False

    def test_empty_source_image_with_attribute(self):
        from viewtron import ViewtronEvent
        event = ViewtronEvent(self.AOI_EMPTY_SOURCE)
        assert isinstance(event, IntrusionEntry)
        assert event.source_image_exists() is False
        assert event.get_source_image_bytes() is None

    def test_empty_target_image_with_attribute(self):
        from viewtron import ViewtronEvent
        event = ViewtronEvent(self.AOI_EMPTY_TARGET)
        assert isinstance(event, IntrusionEntry)
        assert event.target_image_exists() is False

    def test_empty_element_without_attribute_is_not_literal_none(self):
        from viewtron import ViewtronEvent
        xml = self.AOI_EMPTY_SOURCE.replace(
            '<sourceBase64Data type="string"><![CDATA[]]></sourceBase64Data>',
            '<sourceBase64Data/>')
        event = ViewtronEvent(xml)
        assert event.source_image_exists() is False
        assert event.get_source_image() is None

    def test_face_and_lpr_empty_images(self):
        face = load_fixture("ipc-v1x", "face-detection.xml")
        import re
        face = re.sub(r'(<sourceBase64Data[^>]*>).*?(</sourceBase64Data>)',
                      r'\1\2', face, flags=re.S)
        event = FaceDetection(face)
        assert event.source_image_exists() is False

        lpr = load_fixture("ipc-v1x", "lpr.xml")
        lpr = re.sub(r'(<(target|source)Base64Data[^>]*>).*?(</\2Base64Data>)',
                     r'\1\3', lpr, flags=re.S)
        event = LPR(lpr)
        assert event.images_exist() is False
        assert event.get_plate_number()  # plate still parsed


# ====================== Version variation and unparsed ======================


def rewrite_config_version(xml, version):
    updated, count = re.subn(
        r'(<config\b[^>]*\bversion=")[^"]*"',
        lambda match: match.group(1) + version + '"',
        xml,
        count=1,
    )
    if count == 0 and re.search(r'<config\b[^>]*\bversion="', xml):
        raise AssertionError("config version was not rewritten")
    return updated


def event_snapshot(event):
    """Fields that must stay stable when only the config version changes."""
    if event is None:
        return None
    snap = {
        "class": type(event).__name__,
        "category": getattr(event, "category", None),
        "alarm": event.get_alarm_type(),
        "description": event.get_alarm_description(),
        "format": event.format,
    }
    for name in (
        "get_plate_number",
        "get_plate_group",
        "get_car_brand",
        "get_car_model",
        "get_car_type",
        "get_car_color",
        "get_face_age",
        "get_face_sex",
        "get_channel_id",
    ):
        fn = getattr(event, name, None)
        if callable(fn):
            snap[name] = fn()
    return snap


def _fixture_names(subdir):
    names = []
    folder = os.path.join(FIXTURES_DIR, subdir)
    for name in sorted(os.listdir(folder)):
        if name.endswith(".xml"):
            names.append(name)
    return names


class TestVersionVariation:
    @pytest.mark.parametrize("filename", _fixture_names("nvr-v2"))
    @pytest.mark.parametrize("version", ["2.1.0", "2.9.0"])
    def test_nvr_fixtures_parse_the_same_at_later_2x(self, filename, version):
        original_xml = load_fixture("nvr-v2", filename)
        original = ViewtronEvent(original_xml)
        rewritten = ViewtronEvent(rewrite_config_version(original_xml, version))
        assert event_snapshot(rewritten) == event_snapshot(original)
        if original is not None:
            assert original.format == "v2"
            assert original.config_version == "2.0.0"
            assert rewritten.format == "v2"
            assert rewritten.config_version == version

    @pytest.mark.parametrize("filename", _fixture_names("ipc-v1x"))
    @pytest.mark.parametrize("version", ["1.0", "1.7"])
    def test_ipc_fixtures_parse_the_same_at_1_0_and_1_7(self, filename, version):
        original_xml = load_fixture("ipc-v1x", filename)
        original = ViewtronEvent(original_xml)
        rewritten = ViewtronEvent(rewrite_config_version(original_xml, version))
        assert event_snapshot(rewritten) == event_snapshot(original)
        if original is not None:
            assert original.format == "v1"
            assert rewritten.format == "v1"
            assert rewritten.config_version == version


class TestDefensiveRouting:
    def test_ipc_body_at_2_1_parses(self):
        xml = rewrite_config_version(load_fixture("ipc-v1x", "lpr.xml"), "2.1.0")
        event, reason = _classify_post(xml)
        assert reason is None
        assert isinstance(event, LPR)
        assert event.category == "lpr"
        assert event.get_plate_number() == "ABC1234"
        assert event.get_plate_group() == "whiteList"
        assert event.format == "v2"
        assert event.config_version == "2.1.0"

    def test_uppercase_vehicle_with_plate_list_reaches_vehicle_lpr(self):
        xml = rewrite_config_version(load_fixture("nvr-v2", "vehicle-lpr.xml"), "2.1.0")
        xml = xml.replace("<smartType>vehicle</smartType>", "<smartType>VEHICLE</smartType>")
        event, reason = _classify_post(xml)
        assert reason is None
        assert isinstance(event, VehicleLPR)
        assert event.category == "lpr"
        assert event.get_plate_number() == "JP116D"
        assert event.get_alarm_description() == "License Plate Detection"
        assert event.format == "v2"

    def test_uppercase_vehicle_without_plate_list_is_unparsed(self):
        xml = rewrite_config_version(load_fixture("nvr-v2", "vehicle-lpr.xml"), "2.1.0")
        xml = xml.replace("<smartType>vehicle</smartType>", "<smartType>VEHICLE</smartType>")
        xml = re.sub(r"<licensePlateListInfo>.*</licensePlateListInfo>", "", xml, flags=re.S)
        event, reason = _classify_post(xml)
        assert event is None
        assert reason == "unknown-smartType"

    def test_v2_without_message_type_is_unparsed(self):
        xml = rewrite_config_version(load_fixture("nvr-v2", "vehicle-lpr.xml"), "2.1.0")
        xml = xml.replace("<messageType>alarmData</messageType>", "")
        event, reason = _classify_post(xml)
        assert event is None
        assert reason == "no-messageType"

    def test_other_smart_types_match_case_insensitively(self):
        xml = rewrite_config_version(
            load_fixture("nvr-v2", "region-intrusion.xml"), "2.1.0"
        )
        xml = xml.replace(
            "<smartType>regionIntrusion</smartType>",
            "<smartType>REGIONINTRUSION</smartType>",
        )
        event, reason = _classify_post(xml)
        assert reason is None
        assert type(event).__name__ == "RegionIntrusion"
        assert event.category == "intrusion"
        assert event.get_alarm_description() == "Perimeter Intrusion"

    def test_alarm_status_reason(self):
        event, reason = _classify_post(load_fixture("ipc-v1x", "alarm-status.xml"))
        assert event is None
        assert reason == "alarmStatus"

    def test_parse_error_reason(self):
        event, reason = _classify_post('<?xml version="1.0"?><config>')
        assert event is None
        assert reason == "parse-error"

    def test_unknown_smart_type_reason(self):
        xml = (
            '<?xml version="1.0" encoding="UTF-8"?>'
            '<config version="1.7"><smartType>MOTION</smartType></config>'
        )
        event, reason = _classify_post(xml)
        assert event is None
        assert reason == "unknown-smartType"

    def test_lowercase_ipc_smart_type_keeps_the_same_class(self):
        xml = load_fixture("ipc-v1x", "lpr.xml").replace(
            ">VEHICE<", ">vehice<", 1
        )
        event, reason = _classify_post(xml)
        assert reason is None
        assert isinstance(event, LPR)
        assert event.get_alarm_type() == "vehice"
        assert event.get_plate_number() == "ABC1234"
        assert event.get_alarm_description() == "License Plate Detection"


class TestIpcV21Fixtures:
    def test_plate_fields_and_microsecond_time(self):
        event = ViewtronEvent(load_local("ipc-v2.1", "plate-ib36nl.xml"))
        assert isinstance(event, LPR)
        assert event.category == "lpr"
        assert event.format == "v1"
        assert event.config_version == "1.7"
        assert event.get_alarm_type() == "VEHICE"
        assert event.get_plate_number() == "IB36NL"
        assert event.get_plate_group() == "whiteList"
        assert event.plate_list == "whiteList"
        assert event.direction == "approach"
        assert event.confidence == 99.0
        assert event.vehicle_color == "white"
        assert event.vehicle_brand == "TestBrand"
        assert event.vehicle_type == "saloon car"
        assert event.vehicle_model == "TestModel"
        micros = 1791471201542438
        seconds, rem = divmod(micros, 1_000_000)
        expected = datetime.fromtimestamp(seconds).replace(microsecond=rem)
        assert event.time_stamp_formatted == expected
        assert event.get_time_stamp_formatted() == str(expected)
        assert "1970" not in event.get_time_stamp_formatted()

    def test_blacklist_away_plate(self):
        event = ViewtronEvent(load_local("ipc-v2.1", "plate-blacklist-away.xml"))
        assert isinstance(event, LPR)
        assert event.category == "lpr"
        assert event.format == "v1"
        assert event.config_version == "1.7"
        assert event.get_alarm_type() == "VEHICE"
        assert event.get_plate_number() == "TEST456"
        assert event.get_plate_group() == "blackList"
        assert event.plate_list == "blackList"
        assert event.direction == "away"
        assert event.confidence == 99.0
        assert event.vehicle_color == "white"
        assert event.vehicle_brand == "TestBrand"
        assert event.vehicle_type == "saloon car"
        assert event.vehicle_model == "TestModel"

    def test_unlisted_approach_has_no_list_type(self):
        event = ViewtronEvent(load_local("ipc-v2.1", "plate-unlisted-approach.xml"))
        assert isinstance(event, LPR)
        assert event.get_plate_number() == "TEST123"
        assert event.vehicleListType is None
        assert event.get_plate_group() == ""
        assert event.plate_list is None
        assert event.direction == "approach"
        assert event.confidence == 99.0
        assert event.vehicle_color == "white"
        assert event.vehicle_brand == "TestBrand"
        assert event.vehicle_type == "saloon car"
        assert event.vehicle_model == "TestModel"

    def test_direction_aliases(self):
        xml = load_local("ipc-v2.1", "plate-blacklist-away.xml")
        leave = ViewtronEvent(xml.replace(">away</vehicleDirect>", ">leave</vehicleDirect>"))
        approach = ViewtronEvent(xml.replace(">away</vehicleDirect>", ">approach</vehicleDirect>"))
        unknown = ViewtronEvent(xml.replace(">away</vehicleDirect>", ">sideways</vehicleDirect>"))
        assert leave.direction == "away"
        assert approach.direction == "approach"
        assert unknown.direction is None

    def test_older_ipc_plate_has_list_without_direction(self):
        event = ViewtronEvent(load_fixture("ipc-v1x", "lpr.xml"))
        assert event.get_plate_group() == "whiteList"
        assert event.plate_list == "whiteList"
        assert event.direction is None
        assert event.confidence is None
        assert event.vehicle_color is None
        assert event.vehicle_brand is None
        assert event.vehicle_type is None
        assert event.vehicle_model is None

    def test_nvr_vehicle_fields_keep_getters(self):
        event = ViewtronEvent(load_fixture("nvr-v2", "vehicle-lpr.xml"))
        assert event.get_car_brand() == "GMC"
        assert event.get_car_model() == "GMC_SAVANA"
        assert event.get_car_type() == "mpv"
        assert event.get_car_color() == "white"
        assert event.vehicle_brand == "GMC"
        assert event.vehicle_model == "GMC_SAVANA"
        assert event.vehicle_type == "mpv"
        assert event.vehicle_color == "white"
        assert event.direction is None
        assert event.confidence is None
        assert event.plate_list is None
        assert event.get_plate_group() == ""

    def test_time_unit_by_magnitude(self):
        from viewtron.events import _parse_event_time

        seconds = 1_700_000_000
        assert _parse_event_time(str(seconds)) == datetime.fromtimestamp(seconds)
        millis = seconds * 1000 + 123
        assert _parse_event_time(str(millis)) == datetime.fromtimestamp(seconds).replace(
            microsecond=123_000
        )
        micros = seconds * 1_000_000 + 427999
        assert _parse_event_time(str(micros)) == datetime.fromtimestamp(seconds).replace(
            microsecond=427999
        )
        assert _parse_event_time(str(1_000_000_000_000)) == datetime.fromtimestamp(1_000_000_000)
        assert _parse_event_time(str(1_000_000_000_000_000)) == datetime.fromtimestamp(
            1_000_000_000
        )

    def test_keepalive_without_declaration_is_ignored(self):
        xml = load_local("ipc-v2.1", "keepalive.xml")
        assert "<?xml" not in xml
        assert ViewtronEvent(xml) is None
        event, reason = _classify_post(xml)
        assert event is None
        assert reason is None

    @pytest.mark.parametrize("filename", ["alarm-status-on.xml", "alarm-status-off.xml"])
    def test_alarm_status_reason(self, filename):
        event, reason = _classify_post(load_local("ipc-v2.1", filename))
        assert event is None
        assert reason == "alarmStatus"
