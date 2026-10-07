"""
Viewtron Camera Client — send commands to cameras and manage plate databases.

Uses Basic HTTP authentication to communicate with Viewtron IP cameras.
Supports license plate CRUD operations and device info queries.

Example:
    from viewtron import ViewtronCamera

    camera = ViewtronCamera("192.168.0.20", "admin", "password")

    # Plate management
    camera.add_plate("ABC1234", group="whiteList")
    plates = camera.get_plates(group="whiteList")
    camera.modify_plate("ABC1234", owner="Mike", telephone="555-1234", group="whiteList")
    camera.delete_plate("ABC1234", group="whiteList")

    # Device info
    info = camera.get_device_info()
"""
# Written by Mike Haldas — mike@cctvcamerapros.net — https://www.Viewtron.com

import warnings

import requests
import xmltodict
import re


# Group names accepted by the ``group=`` argument. Ids come from the device.
_GROUP_NAMES = ("whiteList", "blackList", "temporaryList")


class ViewtronAPIError(RuntimeError):
    """The camera rejected a command or returned an HTTP error.

    Subclasses ``RuntimeError`` so existing ``except RuntimeError`` handlers
    still catch API failures.

    Attributes:
        code: Device ``errorCode`` as a string, when the camera sent one.
        desc: Short description. For an empty HTTP 400 body this is
            ``"Invalid Request (HTTP 400, empty body)"``.
        http_status: HTTP status code, or None when the body was HTTP 200
            and the failure is an application errorCode.
    """

    def __init__(self, code, desc, http_status=None):
        self.code = None if code is None else str(code)
        self.desc = "" if desc is None else str(desc)
        self.http_status = http_status
        super().__init__(self.desc)


class UnsupportedFeature(RuntimeError):
    """The connected firmware does not provide this command.

    Raised when the LicensePlates commands are not available. The older
    ``GetVehiclePlate`` / ``AddVehiclePlate`` command family (``listType``,
    ``plateItemType``, ``pageIndex``, ``pageSize``) is not implemented:
    its request and response shape is not confirmed, so this SDK does not
    call those commands.
    """

    def __init__(self, message="plate database API not available on this firmware"):
        super().__init__(message)


class CameraCapabilities:
    """What a camera reports about its API.

    Attributes:
        api_version (str or None): ``apiVersion`` from GetDeviceInfo.
            When that field is missing, GetDeviceDetail is used.
        http_post_version (str or None): ``httpPostVersion`` from
            GetDeviceInfo, with the same GetDeviceDetail fallback.
        config_version (str or None): ``version`` attribute on the
            device's response ``<config>`` element. Outgoing requests
            still use config version 2.1.0.
        supported_apis (frozenset or None): Command names from
            GetSupportedAPIs. None when that command is not available
            (Invalid Request or HTTP 400).
    """

    def __init__(self, api_version, http_post_version, config_version, supported_apis):
        self.api_version = api_version
        self.http_post_version = http_post_version
        self.config_version = config_version
        self.supported_apis = supported_apis

    def __repr__(self):
        return (
            "CameraCapabilities("
            f"api_version={self.api_version!r}, "
            f"http_post_version={self.http_post_version!r}, "
            f"config_version={self.config_version!r}, "
            f"supported_apis={self.supported_apis!r})"
        )


def _xml_value(val):
    """Return an element's text, ignoring type attributes."""
    if isinstance(val, dict):
        text = val.get("#text", "")
        if text in (None, ""):
            text = val.get("value", "")
        return str(text or "").strip()
    return str(val).strip() if val else ""


def _as_list(value):
    if value is None or value == "":
        return []
    if isinstance(value, list):
        return value
    return [value]


class ViewtronCamera:
    """Client for Viewtron IP camera API with Basic HTTP authentication.

    Sends commands to the camera over HTTP. Currently supports license plate
    database management (CRUD), device info, and capability discovery.

    Plate group ids are device-specific. On current firmware (observed on a
    camera running 5.3.1, API 2.1.0) group 1 is ``temporaryList`` and the
    allow list is ``whiteList``, typically group 2. Pass ``group=`` with
    one of ``whiteList``, ``blackList``, or ``temporaryList``. The numeric
    ``group_id`` argument is still accepted. Omitting both uses ``"1"`` and
    warns once per process. A future major release will default to
    ``whiteList``.

    Args:
        host (str): Camera IP address (e.g., "192.168.0.20").
        username (str): Camera admin username.
        password (str): Camera admin password.
        port (int): HTTP port (default 80).

    Example:
        from viewtron import ViewtronCamera

        camera = ViewtronCamera("192.168.0.20", "admin", "password")
        plates = camera.get_plates(group="whiteList")
        for plate in plates:
            print(plate["plate_number"], plate["owner"])
    """

    # Outgoing request config version. Kept at 2.1.0. The version a device
    # reports is available on ``capabilities.config_version`` and is not
    # copied into requests.
    CONFIG_WRAPPER = '<?xml version="1.0" encoding="UTF-8"?><config version="2.1.0" xmlns="http://www.ipc.com/ver10">{body}</config>'

    _default_group_warning_sent = False

    def __init__(self, host, username, password, port=80):
        self.host = host
        self.port = port
        self.username = username
        self.password = password
        self.base_url = f"http://{host}:{port}" if port != 80 else f"http://{host}"
        self._supported_apis = None
        self._supported_apis_loaded = False
        self._capabilities = None
        self._plate_groups = None
        self._plate_backend = None
        self._response_config_version = None

    def _strip_ns(self, text):
        return re.sub(r' xmlns="[^"]*"', '', text or "")

    def _parse_http_response(self, resp):
        """Parse a camera HTTP response. Raises ``ViewtronAPIError`` on HTTP errors."""
        text = resp.text or ""
        status = resp.status_code
        if status == 400 and not text.strip():
            raise ViewtronAPIError(
                "1",
                "Invalid Request (HTTP 400, empty body)",
                http_status=400,
            )
        if status >= 400:
            code = str(status)
            desc = f"HTTP {status}"
            if text.strip():
                try:
                    parsed = xmltodict.parse(self._strip_ns(text))
                except Exception:
                    parsed = None
                config = (parsed or {}).get("config") or {}
                if config.get("@errorCode") is not None:
                    code = str(config.get("@errorCode"))
                if config.get("@errorDesc"):
                    desc = str(config.get("@errorDesc"))
            raise ViewtronAPIError(code, desc, http_status=status)
        if not text.strip():
            raise ViewtronAPIError(None, "Empty response", http_status=status)
        try:
            parsed = xmltodict.parse(self._strip_ns(text))
        except Exception as exc:
            raise ViewtronAPIError(
                None, f"Invalid XML response: {exc}", http_status=status
            ) from exc
        version = str((parsed.get("config") or {}).get("@version") or "")
        if version and not self._response_config_version:
            self._response_config_version = version
        return parsed

    def _post(self, endpoint, body_xml):
        """Send a POST with Basic auth. Returns parsed XML as dict."""
        xml = self.CONFIG_WRAPPER.format(body=body_xml)
        resp = requests.post(
            f"{self.base_url}{endpoint}",
            data=xml.encode("utf-8"),
            headers={"Content-Type": "application/xml"},
            auth=(self.username, self.password),
            timeout=10,
        )
        return self._parse_http_response(resp)

    def _get(self, endpoint):
        """Send a GET with Basic auth. Returns parsed XML as dict."""
        resp = requests.get(
            f"{self.base_url}{endpoint}",
            auth=(self.username, self.password),
            timeout=10,
        )
        return self._parse_http_response(resp)

    def _check_error(self, parsed, operation):
        """Check parsed response for errors. Raises ``ViewtronAPIError`` on failure."""
        config = parsed.get("config", {}) or {}
        error_code = str(config.get("@errorCode", "0"))
        if error_code != "0":
            error_desc = config.get("@errorDesc", "Unknown error")
            raise ViewtronAPIError(
                error_code,
                f"{operation} failed: {error_desc} (code {error_code})",
            )

    def _invalid_request(self, exc):
        return isinstance(exc, ViewtronAPIError) and (
            exc.http_status == 400 or exc.code == "1"
        )

    def _flatten_info(self, info):
        if not isinstance(info, dict):
            return {}
        return {
            k: str(v.get("#text", v) if isinstance(v, dict) else v).strip()
            for k, v in info.items()
        }

    # ========================= DEVICE INFO / CAPABILITIES =========================

    def get_device_info(self):
        """Get camera device information.

        Returns:
            dict with keys like 'deviceName', 'model', 'firmwareVersion',
            'apiVersion', and 'httpPostVersion' when the device sends them.
        """
        parsed = self._get("/GetDeviceInfo")
        info = (parsed.get("config") or {}).get("deviceInfo", {})
        return self._flatten_info(info)

    def get_supported_apis(self):
        """Return the command names advertised by GetSupportedAPIs.

        Names are read from ``applicationInterfaces/item`` and de-duplicated.
        The ``count`` attribute is not trusted: devices have been observed
        (a camera running 5.3.1 firmware, API 2.1.0) reporting a count that
        does not match the number of items, with some names repeated.

        Returns:
            frozenset of command names, or None when the device answers
            Invalid Request (errorCode 1) or HTTP 400. None means the
            command list is unknown (typical of 1.x firmware), not that
            the device has an empty API.

        The result is cached on this instance.
        """
        if self._supported_apis_loaded:
            return self._supported_apis
        try:
            parsed = self._post("/GetSupportedAPIs", "")
        except ViewtronAPIError as exc:
            if self._invalid_request(exc):
                self._supported_apis = None
                self._supported_apis_loaded = True
                return None
            raise
        config = parsed.get("config") or {}
        code = str(config.get("@errorCode", "0"))
        if code == "1":
            self._supported_apis = None
            self._supported_apis_loaded = True
            return None
        if code not in ("0", ""):
            raise ViewtronAPIError(
                code, str(config.get("@errorDesc") or "Unknown error")
            )
        block = config.get("applicationInterfaces") or {}
        names = []
        if isinstance(block, dict):
            for item in _as_list(block.get("item")):
                name = _xml_value(item)
                if name:
                    names.append(name)
        self._supported_apis = frozenset(names)
        self._supported_apis_loaded = True
        return self._supported_apis

    @property
    def capabilities(self):
        """Cached snapshot of api version, HTTP POST version, and commands.

        ``api_version`` and ``http_post_version`` come from GetDeviceInfo.
        If either is missing, GetDeviceDetail (``detail/property``) fills
        the gap. ``config_version`` is the response ``<config version>``.
        ``supported_apis`` is the set from ``get_supported_apis()``.

        Returns:
            CameraCapabilities
        """
        if self._capabilities is not None:
            return self._capabilities

        api_version = None
        http_post_version = None
        config_version = None

        info_parsed = self._optional_get("/GetDeviceInfo")
        if info_parsed:
            config = info_parsed.get("config") or {}
            config_version = str(config.get("@version") or "") or None
            flat = self._flatten_info(config.get("deviceInfo") or {})
            api_version = flat.get("apiVersion") or None
            http_post_version = flat.get("httpPostVersion") or None

        if not api_version or not http_post_version:
            detail_parsed = self._optional_get("/GetDeviceDetail")
            if detail_parsed:
                config = detail_parsed.get("config") or {}
                if not config_version:
                    config_version = str(config.get("@version") or "") or None
                prop = ((config.get("detail") or {}).get("property") or {})
                flat = self._flatten_info(prop)
                if not api_version:
                    api_version = flat.get("apiVersion") or None
                if not http_post_version:
                    http_post_version = flat.get("httpPostVersion") or None

        supported = self.get_supported_apis()
        if not config_version:
            config_version = self._response_config_version

        self._capabilities = CameraCapabilities(
            api_version=api_version,
            http_post_version=http_post_version,
            config_version=config_version,
            supported_apis=supported,
        )
        return self._capabilities

    def _optional_get(self, endpoint):
        try:
            return self._get(endpoint)
        except ViewtronAPIError:
            return None

    # ========================= PLATE DATABASE =========================

    def _ensure_license_plates(self):
        """Use the LicensePlates commands, or raise if this device lacks them.

        When GetSupportedAPIs lists ``GetLicensePlates``, plate methods call
        AddLicensePlates, GetLicensePlates, ModifyLicensePlate, and
        DeleteLicensePlate.

        When the command list is unknown, a read-only GetLicensePlates
        request is sent. Invalid Request or HTTP 400 means the command is
        not available.

        TODO: Firmware that exposes GetVehiclePlate / AddVehiclePlate
        (listType, plateItemType, pageIndex, pageSize) needs a second plate
        backend. That request and response shape is not confirmed, so this
        SDK does not call those commands and raises UnsupportedFeature
        instead.
        """
        if self._plate_backend == "license":
            return
        if self._plate_backend == "missing":
            raise UnsupportedFeature(
                "plate database API not available on this firmware"
            )
        apis = self.get_supported_apis()
        if apis is not None:
            if "GetLicensePlates" in apis:
                self._plate_backend = "license"
                return
            self._plate_backend = "missing"
            raise UnsupportedFeature(
                "plate database API not available on this firmware"
            )
        if self._probe_license_plates():
            self._plate_backend = "license"
            return
        self._plate_backend = "missing"
        raise UnsupportedFeature(
            "plate database API not available on this firmware"
        )

    def _probe_license_plates(self):
        """Read-only GetLicensePlates. True when the command exists."""
        body = (
            "<searchFilter>"
            "<maxResult>1</maxResult>"
            "<resultOffset>1</resultOffset>"
            "<groupId><![CDATA[1]]></groupId>"
            "</searchFilter>"
        )
        try:
            parsed = self._post("/GetLicensePlates", body)
        except ViewtronAPIError as exc:
            if self._invalid_request(exc):
                return False
            return True
        code = str((parsed.get("config") or {}).get("@errorCode", "0"))
        if code == "1":
            return False
        return True

    def _warn_default_group(self):
        if ViewtronCamera._default_group_warning_sent:
            return
        ViewtronCamera._default_group_warning_sent = True
        warnings.warn(
            "Using plate group id '1'. On current firmware (observed on a "
            "camera running 5.3.1, API 2.1.0) group 1 is the temporary list. "
            "The allow list is whiteList, typically group 2. Pass "
            "group='whiteList' or another group_id. This default will change "
            "in a future major release.",
            UserWarning,
            stacklevel=4,
        )

    def _resolve_group_id(self, group, group_id, warn_default):
        if group is not None:
            if group not in _GROUP_NAMES:
                raise ValueError(
                    "group must be 'whiteList', 'blackList', or 'temporaryList'"
                )
            groups = self.get_plate_groups()
            for gid, name in groups.items():
                if name == group:
                    return str(gid)
            raise UnsupportedFeature(
                f"Plate group {group!r} is not available on this firmware"
            )
        if warn_default and str(group_id) == "1":
            self._warn_default_group()
        return str(group_id)

    def get_plate_groups(self):
        """Return plate groups as ``{id: name}`` from GetLicensePlateGroups.

        Ids are ints when they are numeric. On current firmware (observed
        on a camera running 5.3.1, API 2.1.0) the groups are
        ``1`` temporaryList, ``2`` whiteList, and ``3`` blackList. Do not
        hard-code those ids; call this method.

        Returns:
            dict mapping group id to group name.

        Raises:
            UnsupportedFeature: The device has no plate-group command.
            ViewtronAPIError: The camera returned another error.
        """
        if self._plate_groups is not None:
            return dict(self._plate_groups)
        apis = self.get_supported_apis()
        if apis is not None and "GetLicensePlateGroups" not in apis:
            raise UnsupportedFeature(
                "plate database API not available on this firmware"
            )
        try:
            parsed = self._post("/GetLicensePlateGroups", "")
        except ViewtronAPIError as exc:
            if apis is None and self._invalid_request(exc):
                raise UnsupportedFeature(
                    "plate database API not available on this firmware"
                ) from exc
            raise
        config = parsed.get("config") or {}
        code = str(config.get("@errorCode", "0"))
        if code == "1":
            raise UnsupportedFeature(
                "plate database API not available on this firmware"
            )
        if code not in ("0", ""):
            raise ViewtronAPIError(
                code, str(config.get("@errorDesc") or "Unknown error")
            )
        block = config.get("licensePlateGroups") or {}
        items = _as_list(block.get("item")) if isinstance(block, dict) else []
        groups = {}
        for item in items:
            if not isinstance(item, dict):
                continue
            gid = _xml_value(item.get("groupId", item.get("id", "")))
            name = _xml_value(item.get("groupName", item.get("name", "")))
            if not gid:
                continue
            key = int(gid) if gid.isdigit() else gid
            groups[key] = name
        self._plate_groups = groups
        return dict(groups)

    def _fetch_plates_page(self, max_results, offset, group_id):
        """Return ``(plates, total)`` for one GetLicensePlates page.

        errorCode 20 (Resources Not Exist) is an empty page, ``([], 0)``.
        Any other errorCode raises ``ViewtronAPIError``. ``total`` is the
        ``licensePlates`` ``total`` attribute, or None when it is absent.
        """
        body = (
            f"<searchFilter>"
            f"<maxResult>{int(max_results)}</maxResult>"
            f"<resultOffset>{int(offset)}</resultOffset>"
            f"<groupId><![CDATA[{group_id}]]></groupId>"
            f"</searchFilter>"
        )
        parsed = self._post("/GetLicensePlates", body)
        config = parsed.get("config") or {}
        code = str(config.get("@errorCode", "0"))
        if code == "20":
            return [], 0
        if code not in ("0", ""):
            raise ViewtronAPIError(
                code, str(config.get("@errorDesc") or "Unknown error")
            )
        plates_info = config.get("licensePlates") or {}
        if not isinstance(plates_info, dict):
            plates_info = {}
        total_raw = plates_info.get("@total")
        total = int(total_raw) if total_raw not in (None, "") else None
        items = _as_list(plates_info.get("item"))
        plates = []
        for item in items:
            if not isinstance(item, dict):
                continue
            plates.append({
                "plate_number": _xml_value(item.get("licensePlateNumber", "")),
                "group_id": _xml_value(item.get("groupId", "")),
                "begin_time": _xml_value(item.get("beginTime", "")),
                "end_time": _xml_value(item.get("endTime", "")),
                "owner": _xml_value(item.get("carOwner", "")),
                "telephone": _xml_value(item.get("telephone", "")),
            })
        return plates, total

    def _page_group(self, group_id, page_size):
        offset = 1
        collected = []
        while True:
            batch, total = self._fetch_plates_page(page_size, offset, group_id)
            if not batch:
                break
            collected.extend(batch)
            offset += len(batch)
            if total is not None and offset > total:
                break
            if total is None and len(batch) < page_size:
                break
        return collected

    def add_plate(self, plate_number, group_id="1", group=None):
        """Add a plate to the camera database.

        Args:
            plate_number: The license plate (e.g., "ABC1234")
            group_id: Numeric group id. Defaults to ``"1"``. On current
                firmware (observed on a camera running 5.3.1, API 2.1.0)
                group 1 is the temporary list. The allow list is
                ``whiteList``, typically group 2. Relying on this default
                warns once.
            group: ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
                The id is resolved with ``get_plate_groups()``. When set,
                this overrides ``group_id``.

        Returns:
            True if successful

        Raises:
            ViewtronAPIError: The camera rejected the command. The top-level
                errorCode is checked before the per-item code.
            UnsupportedFeature: This firmware has no LicensePlates API.
        """
        self._ensure_license_plates()
        group_id = self._resolve_group_id(group, group_id, warn_default=True)
        body = (
            f'<licensePlates type="list" maxCount="100" count="1">'
            f"<item>"
            f"<index>1</index>"
            f"<licensePlateNumber><![CDATA[{plate_number}]]></licensePlateNumber>"
            f"<groupId><![CDATA[{group_id}]]></groupId>"
            f"</item>"
            f"</licensePlates>"
        )
        parsed = self._post("/AddLicensePlates", body)
        self._check_error(parsed, "AddLicensePlates")
        config = parsed.get("config", {}) or {}
        reply = config.get("licensePlatesReply", {}) or {}
        item = reply.get("item", {})
        if isinstance(item, list):
            item = item[0] if item else {}
        error_code = item.get("errorCode", {})
        code = error_code.get("#text", str(error_code)) if isinstance(error_code, dict) else str(error_code)
        if code != "0":
            raise ViewtronAPIError(code, f"AddLicensePlates failed: error code {code}")
        return True

    def add_plates(self, plate_numbers, group_id="1", group=None):
        """Add multiple plates to the camera database.

        Args:
            plate_numbers: List of plate strings
            group_id: Numeric group id. Defaults to ``"1"`` (the temporary
                list on current firmware; see ``add_plate``). Relying on
                this default warns once.
            group: ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
                Overrides ``group_id`` when set.

        Returns:
            True if all successful

        Raises:
            ViewtronAPIError: The camera rejected the command.
            UnsupportedFeature: This firmware has no LicensePlates API.
        """
        self._ensure_license_plates()
        group_id = self._resolve_group_id(group, group_id, warn_default=True)
        items = ""
        for i, plate in enumerate(plate_numbers, 1):
            items += (
                f"<item>"
                f"<index>{i}</index>"
                f"<licensePlateNumber><![CDATA[{plate}]]></licensePlateNumber>"
                f"<groupId><![CDATA[{group_id}]]></groupId>"
                f"</item>"
            )
        body = f'<licensePlates type="list" maxCount="100" count="{len(plate_numbers)}">{items}</licensePlates>'
        parsed = self._post("/AddLicensePlates", body)
        self._check_error(parsed, "AddLicensePlates")
        return True

    def get_plates(self, max_results=50, offset=1, group_id="1", group=None):
        """Query one page of the plate database.

        Args:
            max_results: Maximum plates to return
            offset: Starting position (1-based — first plate is offset 1)
            group_id: Numeric group id. Defaults to ``"1"``. On current
                firmware (observed on a camera running 5.3.1, API 2.1.0)
                group 1 is the temporary list, so this default does not
                return allow-list plates. The allow list is ``whiteList``,
                typically group 2. Relying on this default warns once.
            group: ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
                Overrides ``group_id`` when set.

        Returns:
            List of plate dicts with keys: plate_number, group_id,
            begin_time, end_time, owner, telephone. An empty database
            (errorCode 20, Resources Not Exist) returns ``[]``.

        Raises:
            ViewtronAPIError: Any errorCode other than 0 or 20, including
                Invalid Request (1) and Range Error (16).
            UnsupportedFeature: This firmware has no LicensePlates API.
        """
        self._ensure_license_plates()
        group_id = self._resolve_group_id(group, group_id, warn_default=True)
        plates, _total = self._fetch_plates_page(max_results, offset, group_id)
        return plates

    def get_all_plates(self, group=None, group_id=None, page_size=50):
        """Return every plate, following ``resultOffset``, ``maxResult``, and ``total``.

        Args:
            group: ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
                When omitted together with ``group_id``, every group from
                ``get_plate_groups()`` is read. That path does not use the
                ``"1"`` default and does not warn.
            group_id: Numeric group id for a single group. Ignored when
                ``group`` is set.
            page_size: Page size sent as ``maxResult``.

        Returns:
            List of plate dicts, in group order then page order.

        Raises:
            ViewtronAPIError: A page returned an error other than 0 or 20.
            UnsupportedFeature: This firmware has no LicensePlates API.
        """
        self._ensure_license_plates()
        if group is None and group_id is None:
            plates = []
            for gid in self.get_plate_groups():
                plates.extend(self._page_group(str(gid), page_size))
            return plates
        if group is not None:
            gid = self._resolve_group_id(group, "1", warn_default=False)
        else:
            gid = str(group_id)
        return self._page_group(gid, page_size)

    def modify_plate(self, plate_number, group_id="1", owner=None, telephone=None, group=None):
        """Update an existing plate's details.

        Args:
            plate_number: Plate to modify (must already exist)
            group_id: Numeric group id. Defaults to ``"1"`` (the temporary
                list on current firmware; see ``add_plate``). Relying on
                this default warns once.
            owner: New owner name (optional)
            telephone: New phone number (optional)
            group: ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
                Overrides ``group_id`` when set.

        Returns:
            True if successful

        Raises:
            ViewtronAPIError: The camera rejected the command.
            UnsupportedFeature: This firmware has no LicensePlates API.
        """
        self._ensure_license_plates()
        group_id = self._resolve_group_id(group, group_id, warn_default=True)
        fields = (
            f"<licensePlateNumber><![CDATA[{plate_number}]]></licensePlateNumber>"
            f"<groupId><![CDATA[{group_id}]]></groupId>"
        )
        if owner is not None:
            fields += f'<carOwner type="string"><![CDATA[{owner}]]></carOwner>'
        if telephone is not None:
            fields += f'<telephone type="string"><![CDATA[{telephone}]]></telephone>'

        body = f"<licensePlate>{fields}</licensePlate>"
        parsed = self._post("/ModifyLicensePlate", body)
        self._check_error(parsed, "ModifyLicensePlate")
        return True

    def delete_plate(self, plate_number, group_id="1", group=None):
        """Delete a plate from the database.

        Args:
            plate_number: Plate to delete
            group_id: Numeric group id. Defaults to ``"1"`` (the temporary
                list on current firmware; see ``add_plate``). Relying on
                this default warns once.
            group: ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
                Overrides ``group_id`` when set.

        Returns:
            True if successful

        Raises:
            ViewtronAPIError: The camera rejected the command.
            UnsupportedFeature: This firmware has no LicensePlates API.
        """
        self._ensure_license_plates()
        group_id = self._resolve_group_id(group, group_id, warn_default=True)
        body = (
            f"<deleteAction>"
            f"<licensePlateNumber><![CDATA[{plate_number}]]></licensePlateNumber>"
            f"<groupId><![CDATA[{group_id}]]></groupId>"
            f"</deleteAction>"
        )
        parsed = self._post("/DeleteLicensePlate", body)
        self._check_error(parsed, "DeleteLicensePlate")
        return True

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        return False

    def __repr__(self):
        return f"ViewtronCamera({self.host})"
