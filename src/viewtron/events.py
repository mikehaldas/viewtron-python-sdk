"""
Viewtron Event Parser — transforms camera HTTP POST XML into Python objects.

Viewtron IP cameras send HTTP POST requests containing XML data when AI
detection events occur (license plate recognition, intrusion detection,
face detection, etc.). This module parses that XML into structured Python
objects with a consistent interface.

Most developers should use ``ViewtronEvent`` (the factory function) or
``ViewtronServer`` rather than instantiating event classes directly.

Example:
    from viewtron import ViewtronEvent

    event = ViewtronEvent(xml_body)
    if event and event.category == "lpr":
        print(event.get_plate_number())
        print(event.get_plate_group())

You can find Viewtron IP cameras at https://www.Viewtron.com
"""
# Written by Mike Haldas — mike@cctvcamerapros.net
import xmltodict
from datetime import datetime as dt
import base64

VT_alarm_types = {
    'MOTION': 'Motion Detection',
    'SENSOR': 'External Sensor',
    'PEA': 'Line Crossing / Intrusion',
    'AVD': 'Exception Detection',
    'OSC': 'Missing Object or Abandoned Object',
    'CDD': 'Crowd Density Detection',
    'VFD': 'Face Detection',
    'VFD_MATCH': 'Face Match',
    'VEHICE': 'License Plate Detection',
    'VEHICLE': 'License Plate Detection',
    'AOIENTRY': 'Intrusion Zone Entry',
    'AOILEAVE': 'Intrusion Zone Exit',
    'LOITER': 'Loitering Detection',
    'PASSLINECOUNT': 'Line Crossing Target Count',
    'TRAFFIC': 'Intrusion Target Count',
    'FALLING': 'Falling Object Detection',
    'EA': 'Motorcycle / Bicycle Detection',
    'VSD': 'Video Metadata',
    'PVD': 'Illegal Parking'
}


def _xml_text(elem):
    """Return an XML element's text as a stripped string.

    xmltodict returns None for an empty element (``<x/>``) and a dict with
    no ``#text`` key for an empty element that has attributes
    (``<x type="string"/>`` or ``<x type="string"><![CDATA[]]></x>``).
    Both become '' here instead of None or the literal string 'None'.
    """
    if isinstance(elem, dict):
        elem = elem.get('#text')
    if elem is None:
        return ''
    return str(elem).strip()


def _parse_event_time(time_text):
    """Return a datetime for a camera ``currentTime`` value.

    The same element is seconds, milliseconds, or microseconds depending
    on firmware. Values at or above 1e15 are microseconds, values at or
    above 1e12 are milliseconds, and smaller values are seconds. Any
    sub-second remainder is kept. Raises ``ValueError`` when ``time_text``
    is missing or not an integer.
    """
    if time_text is None or str(time_text).strip() == '':
        raise ValueError("missing time")
    time_val = int(str(time_text).strip())
    if time_val >= 1_000_000_000_000_000:
        seconds, rem = divmod(time_val, 1_000_000)
        micros = rem
    elif time_val >= 1_000_000_000_000:
        seconds, rem = divmod(time_val, 1_000)
        micros = rem * 1_000
    else:
        seconds, micros = time_val, 0
    stamp = dt.fromtimestamp(seconds)
    if micros:
        stamp = stamp.replace(microsecond=micros)
    return stamp


_DIRECTIONS = {
    "approach": "approach",
    "away": "away",
    "leave": "away",
}

_PLATE_LISTS = {
    "whitelist": "whiteList",
    "blacklist": "blackList",
    "temporarylist": "temporaryList",
    "strangerlist": "strangerList",
}


def _normalize_direction(text):
    """Map a post's direction text to ``approach``, ``away``, or None.

    Documented IPC values are ``approach`` and ``leave``. Posts also send
    ``away``. ``leave`` and ``away`` both become ``away``.
    """
    return _DIRECTIONS.get(str(text or "").strip().casefold())


def _normalize_plate_list(text):
    """Map ``vehicleListType`` to a known list name, or None."""
    return _PLATE_LISTS.get(str(text or "").strip().casefold())


def _plate_confidence(elem):
    """Return PlateConfidence ``count`` as a 0–100 float.

    ``count="9900"`` is 99.00. Missing or non-numeric counts are None.
    """
    if not isinstance(elem, dict):
        return None
    count = elem.get("@count")
    if count in (None, ""):
        return None
    try:
        return float(count) / 100.0
    except (TypeError, ValueError):
        return None


def _optional_text(elem):
    text = _xml_text(elem)
    return text or None


def _lookup_ci(table, smart_type):
    """Return the table key for ``smart_type``, ignoring case when unambiguous."""
    if smart_type in table:
        return smart_type
    folded = str(smart_type).casefold()
    matches = [key for key in table if key.casefold() == folded]
    if len(matches) == 1:
        return matches[0]
    return None


def _alarm_description(table, alarm_type):
    """Look up a description. Exact keys win; otherwise one case-insensitive match."""
    if alarm_type in table:
        return table[alarm_type]
    key = _lookup_ci(table, alarm_type)
    if key is not None:
        return table[key]
    return 'Unknown Alarm'


def _apply_version_fields(event, config):
    """Set ``config_version`` and ``format`` (``v1`` or ``v2``) from the post."""
    version = ''
    if isinstance(config, dict):
        version = config.get('@version', '') or ''
        if isinstance(version, dict):
            version = version.get('#text', '') or ''
    version = str(version)
    event.config_version = version
    event.format = 'v2' if version.startswith('2') else 'v1'


class APIpost:
    """Base class for IPC v1.x camera events.

    Parses common fields shared by all event types: device name, alarm type,
    timestamp, and images. Subclasses add event-specific fields (plate number,
    face attributes, etc.).

    Attributes:
        category (str): Event category set by ViewtronEvent — "lpr", "face",
            "intrusion", "counting", "metadata", or "traject".
        alarm_type (str): Raw alarm type from the camera XML (e.g., "VEHICE",
            "VFD", "PEA").
        alarm_description (str): Human-readable description (e.g.,
            "License Plate Detection").
        ip_cam (str): Camera device name.
        config_version (str): ``version`` attribute from the post's
            ``<config>`` element, such as ``"1.7"`` or ``"2.1.0"``.
        format (str): ``"v1"`` or ``"v2"``, from the major digit of
            ``config_version``. A direct camera post that uses a 2.x
            config version is ``"v2"`` even when its body matches the
            IPC layout.

    Note:
        Do not instantiate directly. Use ``ViewtronEvent(xml)`` instead.
    """

    def __init__(self, post_body, json):
        self.xml = str(post_body)
        self.json = json
        config = json.get('config', {})
        # === SAFE PARSING ===
        types = config.get('types', {})
        self.alarm_types = types.get('openAlramObj', {})
        self.target_types = types.get('targetType', {})
        device_name = config.get('deviceName', {})
        self.ip_cam = (
            device_name.get('#text') if isinstance(device_name, dict) else
            device_name.get('value') if isinstance(device_name, dict) else
            str(device_name or 'Unknown Camera')
        )
        smart_type = config.get('smartType', {})
        self.alarm_type = _xml_text(smart_type)
        self.alarm_description = _alarm_description(VT_alarm_types, self.alarm_type)
        _apply_version_fields(self, config)
        current_time = config.get('currentTime', {})
        time_text = _xml_text(current_time) if isinstance(current_time, dict) else str(current_time or '')
        try:
            self.time_stamp_formatted = _parse_event_time(time_text)
        except Exception:
            self.time_stamp_formatted = dt.now()

    def set_ip_address(self, ip_address):
        self.ip_address = ip_address
        return 1

    def get_ip_address(self):
        return getattr(self, 'ip_address', 'Unknown')

    def get_alarm_types(self):
        return self.alarm_types

    def get_alarm_description(self):
        """Returns human-readable event description (e.g., "License Plate Detection")."""
        return self.alarm_description

    def get_target_types(self):
        """Returns supported target types from the camera (person, car, motor)."""
        return self.target_types

    def get_time_stamp_formatted(self):
        """Returns the camera event time as a string.

        ``currentTime`` is read as seconds, milliseconds, or microseconds
        by magnitude, so a microsecond post is the camera's event time
        rather than the moment the post was parsed.

        Returns:
            str: Timestamp like "2026-10-07 17:24:47.427999".
        """
        return str(self.time_stamp_formatted)

    def get_time_stamp(self):
        """Returns current Unix timestamp as a string (used for filenames).

        Returns:
            str: Unix timestamp like "1775748316".
        """
        return str(int(dt.now().timestamp()))

    def get_ip_cam(self):
        """Returns the camera's device name.

        Returns:
            str: Device name (e.g., "Viewtron IPC").
        """
        return self.ip_cam

    def get_alarm_type(self):
        """Returns the raw alarm type code from the camera XML.

        Returns:
            str: Alarm type (e.g., "VEHICE", "VFD", "PEA", "vehicle").
        """
        return self.alarm_type

    def get_plate_number(self):
        """Returns the detected license plate number.

        Returns:
            str: Plate number (e.g., "ABC1234") or "<NO PLATE EXISTS>"
                if this is not an LPR event.
        """
        return getattr(self, 'plate_number', '<NO PLATE EXISTS>')

    def source_image_exists(self):
        """Returns True if the event contains an overview/scene image.

        Returns:
            bool: True if a base64-encoded overview image is available.
        """
        return getattr(self, 'has_source_image', False) and bool(getattr(self, 'source_image', ''))

    def target_image_exists(self):
        """Returns True if the event contains a target crop image.

        Returns:
            bool: True if a base64-encoded target image is available
                (plate crop for LPR, face crop for face detection).
        """
        return getattr(self, 'has_target_image', False) and bool(getattr(self, 'target_image', ''))

    def images_exist(self):
        """Returns True if the event contains any images.

        Returns:
            bool: True if either overview or target image is available.
        """
        return self.source_image_exists() or self.target_image_exists()

    def get_source_image(self):
        """Returns the overview/scene image as a base64-encoded string.

        Returns:
            str or None: Base64 JPEG data, or None if no image.
        """
        return getattr(self, 'source_image', '') if self.source_image_exists() else None

    def get_target_image(self):
        """Returns the target crop image as a base64-encoded string.

        Returns:
            str or None: Base64 JPEG data (plate crop, face crop, etc.),
                or None if no image.
        """
        return getattr(self, 'target_image', '') if self.target_image_exists() else None

    def get_source_image_bytes(self):
        """Returns the overview/scene image as decoded JPEG bytes.

        Ready to save to disk, publish to MQTT, or include in notifications.

        Returns:
            bytes or None: JPEG image data, or None if no image.
        """
        data = self.get_source_image()
        if data:
            try:
                return base64.b64decode(data)
            except Exception:
                return None
        return None

    def get_target_image_bytes(self):
        """Returns the target crop image as decoded JPEG bytes.

        Ready to save to disk, publish to MQTT, or include in notifications.
        For LPR events this is the plate crop, for face detection it's the
        face crop.

        Returns:
            bytes or None: JPEG image data, or None if no image.
        """
        data = self.get_target_image()
        if data:
            try:
                return base64.b64decode(data)
            except Exception:
                return None
        return None

    def dump_xml(self):
        print(self.xml)

    def dump_json(self):
        print(self.json)


class CommonImagesLocation(APIpost):
    def __init__(self, post_body):
        self.json = xmltodict.parse(post_body)
        config = self.json.get('config', {})
        list_info = config.get('listInfo', {})
        self.has_source_image = self.has_target_image = False
        self.source_image = self.target_image = ''
        if isinstance(list_info, dict) and list_info.get('@count', '0') != '0':
            item = list_info.get('item', {})
            if isinstance(item, list):
                item = item[0] if item else {}
            target_data = item.get('targetImageData', {})
            length = target_data.get('targetBase64Length', {})
            length = length.get('#text', '0') if isinstance(length, dict) else str(length)
            if length and int(length) > 0:
                base64_data = target_data.get('targetBase64Data', {}) or target_data.get('sourceBase64Data', {})
                self.target_image = _xml_text(base64_data)
                self.has_target_image = bool(self.target_image)
        source_info = config.get('sourceDataInfo', {})
        if source_info:
            base64_data = source_info.get('sourceBase64Data', {})
            self.source_image = _xml_text(base64_data)
            self.has_source_image = bool(self.source_image)
        super().__init__(post_body, self.json)

class FaceDetectionImages(APIpost):
    """
    Dedicated image extractor for Face Detection (VFD + FEATURE_RESULT) events.
    Replaces CommonImagesLocation for FaceDetection – images are delivered differently:
      • Full scene image  → in <sourceDataInfo><sourceBase64Data>
      • Face crop(s)      → in each <item><targetImageData><targetBase64Data>
    """
    def __init__(self, post_body):
        self.json = xmltodict.parse(post_body)
        config = self.json.get('config', {})

        # Reset flags and images
        self.has_source_image = False
        self.has_target_image = False
        self.source_image = ''
        self.target_image = ''  # will hold only the FIRST face crop (for backward compatibility)

        # 1. Full-scene image (always in sourceDataInfo for VFD)
        source_info = config.get('sourceDataInfo', {})
        if source_info:
            base64_data = source_info.get('sourceBase64Data', {})
            self.source_image = _xml_text(base64_data)
            self.has_source_image = bool(self.source_image)

        # 2. Face crops – one or more in listInfo/item
        list_info = config.get('listInfo', {})
        items = list_info.get('item', []) if isinstance(list_info, dict) else []
        if not isinstance(items, list):
            items = [items] if items else []

        if items:
            # Use the first face crop as "target_image" to keep APIpost methods working
            first_item = items[0]
            if isinstance(first_item, dict):
                target_data = first_item.get('targetImageData', {})
                length_elem = target_data.get('targetBase64Length', {})
                length = length_elem.get('#text', '0') if isinstance(length_elem, dict) else str(length_elem)
                if length and int(length) > 0:
                    base64_elem = target_data.get('targetBase64Data', {})
                    self.target_image = _xml_text(base64_elem)
                    self.has_target_image = bool(self.target_image)

        super().__init__(post_body, self.json)

class FaceDetection(FaceDetectionImages, APIpost):
    def __init__(self, post_body):
        super().__init__(post_body)

class IntrusionDetection(CommonImagesLocation, APIpost):
    def __init__(self, post_body):
        super().__init__(post_body)

class IntrusionEntry(CommonImagesLocation, APIpost):
    def __init__(self, post_body):
        super().__init__(post_body)

class IntrusionExit(CommonImagesLocation, APIpost):
    def __init__(self, post_body):
        super().__init__(post_body)

class LoiteringDetection(CommonImagesLocation, APIpost):
    def __init__(self, post_body):
        super().__init__(post_body)

class IllegalParking(CommonImagesLocation, APIpost):
    def __init__(self, post_body):
        super().__init__(post_body)


class VideoMetadata(APIpost):
    def __init__(self, post_body):
        self.json = xmltodict.parse(post_body)
        config = self.json.get('config', {})
        vsd = config.get('vsd', {})
        source_info = vsd.get('sourceDataInfo', {})
        length = source_info.get('sourceBase64Length', {})
        Parsed_length = length.get('#text', '0') if isinstance(length, dict) else str(length)
        if Parsed_length and int(Parsed_length) > 0:
            base64_data = source_info.get('sourceBase64Data', {})
            self.source_image = _xml_text(base64_data)
            self.has_source_image = bool(self.source_image)
        target_data = vsd.get('targetImageData', {})
        length = target_data.get('targetBase64Length', {})
        Parsed_length = length.get('#text', '0') if isinstance(length, dict) else str(length)
        if Parsed_length and int(Parsed_length) > 0:
            base64_data = target_data.get('targetBase64Data', {})
            self.target_image = _xml_text(base64_data)
            self.has_target_image = bool(self.target_image)
        super().__init__(post_body, self.json)


class LPR(APIpost):
    """IPC v1.x License Plate Recognition event (smartType: VEHICE/VEHICLE).

    Parses plate number, authorization status, and images from the camera's
    HTTP POST XML.

    Attributes:
        plate_number (str): Detected plate text (e.g., "ABC1234").
        vehicleListType (str or None): Raw ``vehicleListType`` text, or
            None when the element is absent.
        direction (str or None): ``"approach"``, ``"away"``, or None.
            ``leave`` in the post is normalized to ``"away"``.
        confidence (float or None): Detection confidence from 0 to 100.
            ``PlateConfidence count="9900"`` is ``99.0``.
        vehicle_color (str or None): ``carAttr/color`` when present.
        vehicle_brand (str or None): ``carAttr/brand`` when present.
        vehicle_type (str or None): ``carAttr/type`` when present.
        vehicle_model (str or None): ``carAttr/model`` when present.
        plate_list (str or None): ``whiteList``, ``blackList``,
            ``temporaryList``, ``strangerList``, or None.

    Example:
        event = ViewtronEvent(xml_body)
        if event.category == "lpr":
            print(event.get_plate_number())  # "ABC1234"
            print(event.get_plate_group())   # "whiteList"
            print(event.direction, event.confidence, event.plate_list)
    """

    def __init__(self, post_body):
        self.json = xmltodict.parse(post_body)
        config = self.json.get('config', {})

        self.vehicleListType = None
        self.direction = None
        self.confidence = None
        self.vehicle_color = None
        self.vehicle_brand = None
        self.vehicle_type = None
        self.vehicle_model = None
        self.plate_list = None
        list_info = config.get('listInfo', {})
        items = list_info.get('item', [])
        if not isinstance(items, list):
            items = [items] if items else []
        if len(items) >= 2:
            plate_item = items[1]
        elif len(items) == 1:
            plate_item = items[0]
        else:
            plate_item = None

        # vehicleListType is where whiteList or blackList is specified for authorized license plates
        if plate_item and isinstance(plate_item, dict):
            vlt = plate_item.get('vehicleListType')
            if isinstance(vlt, dict):
                self.vehicleListType = vlt.get('#text') or vlt.get('value')
            elif vlt:
                self.vehicleListType = str(vlt)
            self.plate_list = _normalize_plate_list(self.vehicleListType)
            self.direction = _normalize_direction(_xml_text(plate_item.get('vehicleDirect')))
            self.confidence = _plate_confidence(plate_item.get('PlateConfidence'))
            car_attr = plate_item.get('carAttr')
            if isinstance(car_attr, dict):
                self.vehicle_color = _optional_text(car_attr.get('color'))
                self.vehicle_type = _optional_text(car_attr.get('type'))
                self.vehicle_brand = _optional_text(car_attr.get('brand'))
                self.vehicle_model = _optional_text(car_attr.get('model'))
        # ===============================================================================

        self.has_source_image = self.has_target_image = False
        self.source_image = self.target_image = ''
        self.plate_number = '<NO PLATE>'

        for idx, item in enumerate(items):
            if not isinstance(item, dict):
                continue
            # Overview image (item 0)
            if idx == 0:
                img_data = item.get('targetImageData', {})
                length_elem = img_data.get('targetBase64Length', {})
                length = length_elem.get('#text') if isinstance(length_elem, dict) else str(length_elem)
                if length and int(length) > 0:
                    base64_elem = img_data.get('targetBase64Data', {})
                    self.source_image = _xml_text(base64_elem)
                    self.has_source_image = bool(self.source_image)
            # Plate info and image (item 1 or only item)
            if idx == 1 or (idx == 0 and len(items) == 1):
                plate_num = item.get('plateNumber', {})
                self.plate_number = _xml_text(plate_num)

                img_data = item.get('targetImageData', {})
                length_elem = img_data.get('targetBase64Length', {})
                length = length_elem.get('#text') if isinstance(length_elem, dict) else str(length_elem)
                if length and int(length) > 0:
                    base64_elem = img_data.get('targetBase64Data', {})
                    self.target_image = _xml_text(base64_elem)
                    self.has_target_image = bool(self.target_image)

        # === FALLBACK: some firmware puts overview in sourceDataInfo ===
        if not self.has_source_image:
            source_info = config.get('sourceDataInfo', {})
            if source_info:
                base64_data = source_info.get('sourceBase64Data', {})
                src = _xml_text(base64_data)
                if src:
                    self.source_image = src
                    self.has_source_image = True

        super().__init__(post_body, self.json)

    def get_plate_group(self):
        """Returns the plate's database group from the IPC camera.

        The IPC camera uses fixed group names in the XML vehicleListType field.
        The application decides what each group means.

        Returns:
            str: Plate group — "whiteList", "blackList", "temporaryList",
                or empty string if the plate is not in the camera's database.

        IPC camera group values (raw XML values, not UI labels):
            - "whiteList" — camera UI shows this as "Allow list"
            - "blackList" — camera UI shows this as "Block list"
            - "temporaryList" — camera UI shows this as "Temporary vehicle"
            - "" (empty) — plate is not in the database, or temporary plate
              with an expired date range
        """
        return self.vehicleListType or ""


# ====================== NVR v2.0 FORMAT ======================
# NVRs send a completely different XML structure than IPC v1.x cameras.
# v2.0 uses: messageType, deviceInfo (ip/mac/channelId), microsecond timestamps,
# sourceDataInfo for overview images, and targetListInfo for target crops.
# These classes expose the SAME method interface as APIpost so server.py
# can process both versions with the same image saving / CSV logging code.

VT_alarm_types_v2 = {
    'regionIntrusion': 'Perimeter Intrusion',
    'lineCrossing': 'Line Crossing',
    'targetCountingByLine': 'Target Counting by Line',
    'targetCountingByArea': 'Target Counting by Area',
    'videoMetadata': 'Video Metadata',
    'vehicle': 'License Plate Detection',
    'videoFaceDetect': 'Face Detection',
}

class APIpostV2:
    """Base class for NVR v2.0 HTTP Posts.

    Attributes:
        config_version (str): ``version`` attribute from the post, such
            as ``"2.0.0"`` or ``"2.1.0"``.
        format (str): ``"v2"`` when ``config_version`` starts with ``2``,
            otherwise ``"v1"``.
    """
    def __init__(self, post_body, json):
        self.xml = str(post_body)
        self.json = json
        config = json.get('config', {})

        # === DEVICE INFO ===
        device_info = config.get('deviceInfo', {})
        device_name = device_info.get('deviceName', 'Unknown Camera')
        # CDATA values come through as plain strings in xmltodict
        self.ip_cam = str(device_name) if device_name else 'Unknown Camera'
        self.device_ip = str(device_info.get('ip', ''))
        self.device_mac = str(device_info.get('mac', ''))
        self.channel_id = str(device_info.get('channelId', ''))

        # === ALARM TYPE ===
        self.alarm_type = str(config.get('smartType', '')).strip()
        self.alarm_description = _alarm_description(VT_alarm_types_v2, self.alarm_type)
        _apply_version_fields(self, config)

        # === TIMESTAMP (seconds, milliseconds, or microseconds) ===
        current_time = config.get('currentTime', '')
        time_text = _xml_text(current_time) if isinstance(current_time, dict) else str(current_time or '')
        try:
            self.time_stamp_formatted = _parse_event_time(time_text)
        except Exception:
            self.time_stamp_formatted = dt.now()

        # === IMAGES ===
        self.has_source_image = False
        self.has_target_image = False
        self.source_image = ''
        self.target_image = ''

        # Overview / scene image in sourceDataInfo
        source_info = config.get('sourceDataInfo', {})
        if source_info:
            length = source_info.get('sourceBase64Length', '0')
            if isinstance(length, dict):
                length = length.get('#text', '0')
            if length and int(length) > 0:
                base64_data = source_info.get('sourceBase64Data', '')
                if isinstance(base64_data, dict):
                    base64_data = base64_data.get('#text', '') or base64_data.get('value', '')
                self.source_image = str(base64_data).strip()
                self.has_source_image = bool(self.source_image)

        # Target crop in targetListInfo (first item only, like v1.x)
        target_list = config.get('targetListInfo', {})
        items = target_list.get('item', []) if isinstance(target_list, dict) else []
        if not isinstance(items, list):
            items = [items] if items else []
        if items:
            first_item = items[0]
            if isinstance(first_item, dict):
                target_data = first_item.get('targetImageData', {})
                length = target_data.get('targetBase64Length', '0')
                if isinstance(length, dict):
                    length = length.get('#text', '0')
                if length and int(length) > 0:
                    base64_data = target_data.get('targetBase64Data', '')
                    if isinstance(base64_data, dict):
                        base64_data = base64_data.get('#text', '') or base64_data.get('value', '')
                    self.target_image = str(base64_data).strip()
                    self.has_target_image = bool(self.target_image)

    # === SAME INTERFACE AS APIpost ===
    def set_ip_address(self, ip_address):
        self.ip_address = ip_address
        return 1

    def get_ip_address(self):
        return getattr(self, 'ip_address', 'Unknown')

    def get_alarm_type(self):
        return self.alarm_type

    def get_alarm_description(self):
        return self.alarm_description

    def get_ip_cam(self):
        return self.ip_cam

    def get_time_stamp(self):
        return str(int(dt.now().timestamp()))

    def get_time_stamp_formatted(self):
        return str(self.time_stamp_formatted)

    def get_plate_number(self):
        return '<NO PLATE EXISTS>'

    def get_plate_group(self):
        return ""

    def source_image_exists(self):
        return self.has_source_image and bool(self.source_image)

    def target_image_exists(self):
        return self.has_target_image and bool(self.target_image)

    def images_exist(self):
        return self.source_image_exists() or self.target_image_exists()

    def get_source_image(self):
        return self.source_image if self.source_image_exists() else None

    def get_target_image(self):
        return self.target_image if self.target_image_exists() else None

    def get_source_image_bytes(self):
        """Returns the overview/scene image as decoded JPEG bytes.

        Returns:
            bytes or None: JPEG image data, or None if no image.
        """
        data = self.get_source_image()
        if data:
            try:
                return base64.b64decode(data)
            except Exception:
                return None
        return None

    def get_target_image_bytes(self):
        """Returns the target crop image as decoded JPEG bytes.

        Returns:
            bytes or None: JPEG image data, or None if no image.
        """
        data = self.get_target_image()
        if data:
            try:
                return base64.b64decode(data)
            except Exception:
                return None
        return None

    def get_channel_id(self):
        return self.channel_id

    def dump_xml(self):
        print(self.xml)

    def dump_json(self):
        print(self.json)


class RegionIntrusion(APIpostV2):
    def __init__(self, post_body):
        json = xmltodict.parse(post_body)
        super().__init__(post_body, json)


class LineCrossing(APIpostV2):
    def __init__(self, post_body):
        json = xmltodict.parse(post_body)
        super().__init__(post_body, json)


class TargetCountingByLine(APIpostV2):
    def __init__(self, post_body):
        json = xmltodict.parse(post_body)
        super().__init__(post_body, json)


class TargetCountingByArea(APIpostV2):
    def __init__(self, post_body):
        json = xmltodict.parse(post_body)
        super().__init__(post_body, json)


class VideoMetadataV2(APIpostV2):
    def __init__(self, post_body):
        json = xmltodict.parse(post_body)
        super().__init__(post_body, json)


class VehicleLPR(APIpostV2):
    """NVR v2.0 License Plate Recognition (smartType: vehicle).

    Uses a completely different XML structure from other v2.0 alarm types:
    - licensePlateListInfo instead of eventInfo + targetListInfo
    - Plate number in licensePlateAttribute/licensePlateNumber
    - Vehicle attributes: carType, color, brand, model
    - Plate database match in licensePlateMatchInfo (groupName, carOwner, etc.)
    - Target image is a plate crop inside licensePlateListInfo/item/targetImageData

    Attributes:
        group_name (str): NVR plate group name (e.g., "Whitelist", "Residents").
            Empty string if the plate is not in the NVR database.
            NVR groups are user-defined — unlike IPC cameras which use fixed
            whiteList/blackList/temporaryList values.
        car_owner (str): Owner name from the NVR plate database.
        direction (str or None): ``"approach"``, ``"away"``, or None.
        confidence (float or None): 0–100 detection confidence, or None.
        vehicle_color, vehicle_brand, vehicle_type, vehicle_model:
            Vehicle attributes from ``carAttribute``. Empty values are None.
            ``get_car_color()`` and the other car getters still return strings.
        plate_list (str or None): ``whiteList``, ``blackList``,
            ``temporaryList``, or ``strangerList`` when the NVR group name
            is one of those lists. A custom group name stays on
            ``get_plate_group()`` and ``plate_list`` is None.
    """
    def __init__(self, post_body):
        json = xmltodict.parse(post_body)
        super().__init__(post_body, json)
        config = json.get('config', {})

        self.plate_number = '<NO PLATE>'
        self.plate_color = ''
        self.car_type = ''
        self.car_color = ''
        self.car_brand = ''
        self.car_model = ''
        self.group_name = ''
        self.car_owner = ''
        self.direction = None
        self.confidence = None
        self.vehicle_color = None
        self.vehicle_brand = None
        self.vehicle_type = None
        self.vehicle_model = None
        self.plate_list = None

        # Parse licensePlateListInfo
        plate_list = config.get('licensePlateListInfo', {})
        items = plate_list.get('item', []) if isinstance(plate_list, dict) else []
        if not isinstance(items, list):
            items = [items] if items else []

        if items:
            first_item = items[0]
            if isinstance(first_item, dict):
                # Plate number and color
                plate_attr = first_item.get('licensePlateAttribute', {})
                if plate_attr:
                    plate_num = plate_attr.get('licensePlateNumber', '')
                    self.plate_number = str(plate_num).strip() if plate_num else '<NO PLATE>'
                    self.plate_color = str(plate_attr.get('color', '')).strip()

                # Vehicle attributes
                car_attr = first_item.get('carAttribute', {})
                if car_attr:
                    self.car_type = str(car_attr.get('carType', '')).strip()
                    self.car_color = str(car_attr.get('color', '')).strip()
                    self.car_brand = str(car_attr.get('brand', '')).strip()
                    self.car_model = str(car_attr.get('model', '')).strip()
                    self.vehicle_type = _optional_text(car_attr.get('carType'))
                    self.vehicle_color = _optional_text(car_attr.get('color'))
                    self.vehicle_brand = _optional_text(car_attr.get('brand'))
                    self.vehicle_model = _optional_text(car_attr.get('model'))

                # Plate database match (NVR user-defined groups)
                match_info = first_item.get('licensePlateMatchInfo', {})
                if match_info:
                    self.group_name = str(match_info.get('groupName', '')).strip()
                    self.car_owner = str(match_info.get('carOwner', '')).strip()
                    self.plate_list = _normalize_plate_list(self.group_name)

                # Plate crop image (inside licensePlateListInfo, not targetListInfo)
                target_data = first_item.get('targetImageData', {})
                if target_data:
                    length = target_data.get('targetBase64Length', '0')
                    if isinstance(length, dict):
                        length = length.get('#text', '0')
                    if length and int(length) > 0:
                        base64_data = target_data.get('targetBase64Data', '')
                        if isinstance(base64_data, dict):
                            base64_data = base64_data.get('#text', '') or base64_data.get('value', '')
                        self.target_image = str(base64_data).strip()
                        self.has_target_image = bool(self.target_image)

    def get_plate_number(self):
        """Returns the detected license plate number.

        Returns:
            str: Plate number (e.g., "ABC1234") or "<NO PLATE>".
        """
        return self.plate_number

    def get_plate_color(self):
        """Returns the detected plate color (e.g., "blue", "yellow").

        Returns:
            str: Plate color, or empty string if not detected.
        """
        return self.plate_color

    def get_car_type(self):
        """Returns the detected vehicle type (e.g., "sedan", "SUV", "truck").

        Returns:
            str: Vehicle type, or empty string if not detected.
        """
        return self.car_type

    def get_car_color(self):
        """Returns the detected vehicle color.

        Returns:
            str: Vehicle color, or empty string if not detected.
        """
        return self.car_color

    def get_car_brand(self):
        """Returns the detected vehicle brand (e.g., "Toyota", "Ford").

        Returns:
            str: Vehicle brand, or empty string if not detected.
        """
        return self.car_brand

    def get_car_model(self):
        """Returns the detected vehicle model.

        Returns:
            str: Vehicle model, or empty string if not detected.
        """
        return self.car_model

    def get_plate_group(self):
        """Returns the plate's database group from the NVR.

        NVR plate groups are user-defined — you create groups and name them
        whatever you want (e.g., "Whitelist", "Residents", "Banned").
        The application decides what each group means.

        Returns:
            str: Group name, or empty string if the plate is not in the
                NVR database.
        """
        return self.group_name

    def get_car_owner(self):
        """Returns the owner name from the NVR plate database.

        Returns:
            str: Owner name, or empty string if not set.
        """
        return self.car_owner


class FaceDetectionV2(APIpostV2):
    """NVR v2.0 Face Detection (smartType: videoFaceDetect).

    Uses faceListInfo instead of eventInfo + targetListInfo.
    Each face item includes attributes: age, sex, glasses, mask.
    Target image is a square face crop inside faceListInfo/item/targetImageData.
    """
    def __init__(self, post_body):
        json = xmltodict.parse(post_body)
        super().__init__(post_body, json)
        config = json.get('config', {})

        self.face_age = ''
        self.face_sex = ''
        self.face_glasses = ''
        self.face_mask = ''

        # Parse faceListInfo
        face_list = config.get('faceListInfo', {})
        items = face_list.get('item', []) if isinstance(face_list, dict) else []
        if not isinstance(items, list):
            items = [items] if items else []

        if items:
            first_item = items[0]
            if isinstance(first_item, dict):
                # Face attributes
                self.face_age = str(first_item.get('age', '')).strip()
                self.face_sex = str(first_item.get('sex', '')).strip()
                self.face_glasses = str(first_item.get('glasses', '')).strip()
                self.face_mask = str(first_item.get('mask', '')).strip()

                # Face crop image (inside faceListInfo, not targetListInfo)
                target_data = first_item.get('targetImageData', {})
                if target_data:
                    length = target_data.get('targetBase64Length', '0')
                    if isinstance(length, dict):
                        length = length.get('#text', '0')
                    if length and int(length) > 0:
                        base64_data = target_data.get('targetBase64Data', '')
                        if isinstance(base64_data, dict):
                            base64_data = base64_data.get('#text', '') or base64_data.get('value', '')
                        self.target_image = str(base64_data).strip()
                        self.has_target_image = bool(self.target_image)

    def get_face_age(self):
        """Returns estimated age of the detected face.

        Returns:
            str: Age estimate (e.g., "25"), or empty string.
        """
        return self.face_age

    def get_face_sex(self):
        """Returns estimated sex of the detected face.

        Returns:
            str: "male" or "female", or empty string.
        """
        return self.face_sex

    def get_face_glasses(self):
        """Returns whether the detected face is wearing glasses.

        Returns:
            str: "yes" or "no", or empty string.
        """
        return self.face_glasses

    def get_face_mask(self):
        """Returns whether the detected face is wearing a mask.

        Returns:
            str: "yes" or "no", or empty string.
        """
        return self.face_mask


# ====================== TRAJECT (Smart Tracking) ======================
# High-volume continuous tracking data sent by cameras with AI detection.
# Each post contains one or more tracked targets with position, type, and velocity.

class Traject:
    """Parsed traject (smart tracking) event from a Viewtron camera.

    Traject posts are high-volume — cameras send them multiple times per second
    for each tracked target. Each post contains target ID, type (person/car/motor),
    bounding box, velocity, and direction.

    Attributes:
        category: Always "traject"
        targets: List of dicts with keys: target_id, target_type, rect, velocity, direction
        device_name: Camera name from the post
        mac: Camera MAC address
        timestamp: Event timestamp
        config_version: ``version`` attribute from the post
        format: ``"v1"`` or ``"v2"``
    """

    def __init__(self, post_body):
        self.xml = str(post_body)
        self.category = "traject"
        self.targets = []
        self.device_name = ""
        self.mac = ""
        self.time_stamp_formatted = ""
        self.source = "IPC"
        self.config_version = ""
        self.format = "v1"

        try:
            data = xmltodict.parse(post_body)
        except Exception:
            return

        config = data.get('config', {})
        _apply_version_fields(self, config)
        version = config.get('@version', '')

        # Device info
        if version.startswith('2'):
            self.source = "NVR"
            device_info = config.get('deviceInfo', {})
            self.device_name = str(device_info.get('deviceName', '')).strip()
            self.mac = str(device_info.get('mac', '')).strip()
            ch = device_info.get('channelId', '')
            if ch:
                self.source = f"NVR-ch{ch}"
        else:
            device_name = config.get('deviceName', {})
            if isinstance(device_name, dict):
                self.device_name = (device_name.get('#text') or device_name.get('value') or '').strip()
            else:
                self.device_name = str(device_name).strip()
            mac = config.get('mac', {})
            if isinstance(mac, dict):
                self.mac = (mac.get('#text') or mac.get('value') or '').strip()
            else:
                self.mac = str(mac).strip()

        # Timestamp
        current_time = config.get('currentTime', {})
        time_text = _xml_text(current_time) if isinstance(current_time, dict) else str(current_time or '')
        try:
            self.time_stamp_formatted = str(_parse_event_time(time_text))
        except Exception:
            self.time_stamp_formatted = str(dt.now())

        # Parse traject items
        traject_data = config.get('traject', {})
        items = traject_data.get('item', []) if isinstance(traject_data, dict) else []
        if not isinstance(items, list):
            items = [items] if items else []

        for item in items:
            if not isinstance(item, dict):
                continue

            def _text(val):
                if isinstance(val, dict):
                    return (val.get('#text') or val.get('value') or str(val)).strip()
                return str(val).strip() if val else ''

            tid = _text(item.get('targetId', ''))
            ttype = _text(item.get('targetType', ''))

            rect = item.get('rect', {})
            x1 = _text(rect.get('x1', '0'))
            y1 = _text(rect.get('y1', '0'))
            x2 = _text(rect.get('x2', '0'))
            y2 = _text(rect.get('y2', '0'))

            velocity = _text(item.get('velocity', '0'))
            direction = _text(item.get('direction', '0'))

            self.targets.append({
                'target_id': tid,
                'target_type': ttype,
                'rect': {'x1': x1, 'y1': y1, 'x2': x2, 'y2': y2},
                'velocity': velocity,
                'direction': direction,
            })

    def get_alarm_type(self):
        return "traject"

    def get_alarm_description(self):
        return "Smart Tracking"

    def get_ip_cam(self):
        return self.device_name

    def get_time_stamp(self):
        return str(int(dt.now().timestamp()))

    def get_time_stamp_formatted(self):
        return self.time_stamp_formatted


# ====================== EVENT FACTORY ======================
# Single entry point for parsing any HTTP POST from a Viewtron camera or NVR.
# Detects the API version and event type, returns the correct class instance.

_IPC_CLASS_LOOKUP = {
    'VEHICE': LPR,
    'VEHICLE': LPR,
    'VFD': FaceDetection,
    'VFD_MATCH': FaceDetection,
    'PEA': IntrusionDetection,
    'AOIENTRY': IntrusionEntry,
    'AOILEAVE': IntrusionExit,
    'LOITER': LoiteringDetection,
    'PVD': IllegalParking,
    'VSD': VideoMetadata,
    'PASSLINECOUNT': IntrusionDetection,
    'TRAFFIC': IntrusionDetection,
}

_NVR_CLASS_LOOKUP = {
    'vehicle': VehicleLPR,
    'videoFaceDetect': FaceDetectionV2,
    'regionIntrusion': RegionIntrusion,
    'lineCrossing': LineCrossing,
    'targetCountingByLine': TargetCountingByLine,
    'targetCountingByArea': TargetCountingByArea,
    'videoMetadata': VideoMetadataV2,
}

_CATEGORY_MAP_IPC = {
    'VEHICE': 'lpr', 'VEHICLE': 'lpr',
    'VFD': 'face', 'VFD_MATCH': 'face',
    'PEA': 'intrusion',
    'AOIENTRY': 'intrusion', 'AOILEAVE': 'intrusion',
    'LOITER': 'intrusion',
    'PVD': 'intrusion',
    'VSD': 'metadata',
    'PASSLINECOUNT': 'counting', 'TRAFFIC': 'counting',
}

_CATEGORY_MAP_NVR = {
    'vehicle': 'lpr',
    'videoFaceDetect': 'face',
    'regionIntrusion': 'intrusion',
    'lineCrossing': 'intrusion',
    'targetCountingByLine': 'counting',
    'targetCountingByArea': 'counting',
    'videoMetadata': 'metadata',
}


def ViewtronEvent(post_body):
    """Parse any HTTP POST body from a Viewtron camera or NVR.

    Single entry point for the SDK. Takes the raw XML string from a camera's
    HTTP POST, detects the API version and event type, and returns the
    correct parsed event object.

    Args:
        post_body (str): Raw XML string from the camera's HTTP POST body.

    Returns:
        Event object with a ``.category`` attribute, or None.

        Possible categories and their event classes:

        - ``"lpr"`` — LPR (v1.x) or VehicleLPR (v2.0). Plate number,
          authorization status, vehicle attributes, images.
        - ``"face"`` — FaceDetection (v1.x) or FaceDetectionV2 (v2.0).
          Age, sex, glasses, mask attributes.
        - ``"intrusion"`` — IntrusionDetection, IntrusionEntry,
          IntrusionExit, RegionIntrusion, LineCrossing.
        - ``"counting"`` — TargetCountingByLine, TargetCountingByArea.
        - ``"metadata"`` — VideoMetadata (v1.x) or VideoMetadataV2 (v2.0).
        - ``"traject"`` — Traject. High-volume tracking data with target
          IDs, types, and bounding boxes.
        - None — Keepalives, alarm status messages, unrecognized events.

        Every returned event has ``config_version`` (the post's config
        ``version`` attribute, for example ``"2.1.0"``) and ``format``
        (``"v1"`` or ``"v2"``). ``ViewtronServer`` reports posts that stay
        None through its ``on_unparsed`` callback.

    Example:
        from viewtron import ViewtronEvent

        event = ViewtronEvent(xml_body)
        if event is None:
            return  # keepalive or unrecognized

        print(event.category)               # "lpr"
        print(event.get_alarm_type())       # "VEHICE"
        print(event.get_alarm_description()) # "License Plate Detection"

        if event.category == "lpr":
            print(event.get_plate_number())      # "ABC1234"
            print(event.get_plate_group())       # "whiteList"
    """
    event, _reason = _classify_post(post_body)
    return event


def _ipc_alarm_type(config):
    """IPC smartType text, or None when the element is absent.

    Matches the historical v1.x extraction: a dict uses ``#text`` and
    falls back to ``str(dict)`` so existing posts keep the same type.
    """
    st = config.get('smartType')
    if st is None:
        return None
    if isinstance(st, dict):
        return (st.get('#text') or str(st)).strip()
    return str(st).strip()


def _has_license_plate_list(config):
    return config.get('licensePlateListInfo') is not None


def _ipc_key_without_message_type(smart_type):
    """IPC class key for a version-2 post that has no messageType.

    An exact IPC key is used as-is, which is how an IPC-style body posted
    with config version 2.x is recognized. A case-insensitive match is
    used only when that spelling is not also an NVR smartType, so a v2
    ``vehicle`` post is not read as an IPC ``VEHICLE`` event.
    """
    if not smart_type:
        return None
    if smart_type in _IPC_CLASS_LOOKUP:
        return smart_type
    key = _lookup_ci(_IPC_CLASS_LOOKUP, smart_type)
    if key is None:
        return None
    if _lookup_ci(_NVR_CLASS_LOOKUP, smart_type) is not None:
        return None
    return key


def _build_ipc_event(post_body, key):
    event = _IPC_CLASS_LOOKUP[key](post_body)
    event.category = _CATEGORY_MAP_IPC.get(key, 'other')
    return event


def _build_nvr_event(post_body, key):
    event = _NVR_CLASS_LOOKUP[key](post_body)
    event.category = _CATEGORY_MAP_NVR.get(key, 'other')
    return event


def _classify_post(post_body):
    """Return ``(event, reason)``.

    ``reason`` is None for a parsed event or a keepalive. Otherwise it is
    one of ``unknown-smartType``, ``no-messageType``, ``parse-error``, or
    ``alarmStatus``. ``ViewtronEvent`` returns only the event.
    ``ViewtronServer`` passes ``reason`` to ``on_unparsed``.
    """
    if not post_body or '<?xml' not in post_body:
        return None, None

    # Traject data (high-volume continuous tracking)
    if '<traject type="list"' in post_body:
        return Traject(post_body), None

    # Alarm status on/off messages are not detection events.
    if 'alarmStatusInfo' in post_body:
        return None, 'alarmStatus'

    try:
        data = xmltodict.parse(post_body)
    except Exception:
        return None, 'parse-error'

    config = data.get('config', {})
    if not config:
        return None, None

    version = str(config.get('@version', '') or '')

    if version.startswith('2'):
        msg_type = config.get('messageType')
        msg_text = str(msg_type).strip() if msg_type is not None else ''
        if msg_text == 'keepalive':
            return None, None
        if msg_text != 'alarmData':
            # No messageType, but an IPC smartType: the body is the older
            # camera layout inside a 2.x envelope.
            alarm_type = _ipc_alarm_type(config)
            if not msg_text and alarm_type:
                key = _ipc_key_without_message_type(alarm_type)
                if key is not None:
                    return _build_ipc_event(post_body, key), None
            return None, 'no-messageType'

        raw = config.get('smartType', '')
        if isinstance(raw, dict):
            smart_type = (raw.get('#text') or str(raw)).strip()
        else:
            smart_type = str(raw).strip()
        key = _lookup_ci(_NVR_CLASS_LOOKUP, smart_type)
        if key is None:
            return None, 'unknown-smartType'
        # ``VEHICLE`` matches the v2 ``vehicle`` class only when the post
        # actually carries the v2 plate list. Otherwise leave it unparsed.
        if key.casefold() == 'vehicle' and not _has_license_plate_list(config):
            return None, 'unknown-smartType'
        return _build_nvr_event(post_body, key), None

    # IPC v1.x format. No smartType is a keepalive (device info only).
    alarm_type = _ipc_alarm_type(config)
    if alarm_type is None or alarm_type == '':
        return None, None
    key = _lookup_ci(_IPC_CLASS_LOOKUP, alarm_type)
    if key is None:
        return None, 'unknown-smartType'
    return _build_ipc_event(post_body, key), None
