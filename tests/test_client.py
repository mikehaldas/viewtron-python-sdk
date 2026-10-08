"""Mocked ViewtronCamera tests for API 2.1 plate groups, errors, and capabilities."""

import warnings
from datetime import datetime, timedelta

import pytest

from viewtron.client import (
    CameraCapabilities,
    UnsupportedFeature,
    ViewtronAPIError,
    ViewtronCamera,
)


HOST = "203.0.113.10"


def xml_config(body, version="2.1.0", **attrs):
    extra = "".join(f' {key}="{value}"' for key, value in attrs.items())
    return (
        '<?xml version="1.0" encoding="UTF-8"?>'
        f'<config version="{version}" xmlns="http://www.ipc.com/ver10"{extra}>'
        f"{body}</config>"
    )


def supported_xml(names, count=111):
    items = "".join(f"<item><![CDATA[{name}]]></item>" for name in names)
    body = (
        f'<applicationInterfaces type="list" count="{count}">'
        '<itemType type="string" maxLen="63"/>'
        f"{items}</applicationInterfaces>"
    )
    return xml_config(body)


PLATE_API_NAMES = [
    "GetDeviceInfo",
    "GetLicensePlates",
    "GetLicensePlates",
    "AddLicensePlates",
    "GetLicensePlateGroups",
    "ModifyLicensePlate",
    "DeleteLicensePlate",
    "GetDeviceInfo",
    "GetDeviceDetail",
]


def groups_xml():
    items = []
    for gid, name in ((1, "temporaryList"), (2, "whiteList"), (3, "blackList")):
        items.append(
            "<item>"
            f'<groupId type="string"><![CDATA[{gid}]]></groupId>'
            f'<groupName type="string"><![CDATA[{name}]]></groupName>'
            "</item>"
        )
    body = (
        '<licensePlateGroups type="list" count="3">'
        + "".join(items)
        + "</licensePlateGroups>"
    )
    return xml_config(body)


def error_xml(code, desc):
    return xml_config("", errorCode=str(code), errorDesc=desc, status="failed")


def plate_xml(plate, group_id, total=1, owner="Ada"):
    body = (
        f'<licensePlates type="list" total="{total}" count="1">'
        "<item>"
        f'<licensePlateNumber type="string"><![CDATA[{plate}]]></licensePlateNumber>'
        f'<groupId type="string"><![CDATA[{group_id}]]></groupId>'
        '<beginTime type="string"><![CDATA[2026-01-01 00:00:00]]></beginTime>'
        '<endTime type="string"><![CDATA[2026-12-31 00:00:00]]></endTime>'
        f'<carOwner type="string"><![CDATA[{owner}]]></carOwner>'
        '<telephone type="string"><![CDATA[555-0100]]></telephone>'
        "</item></licensePlates>"
    )
    return xml_config(body)


def plates_page_xml(rows, total):
    items = []
    for plate, group_id in rows:
        items.append(
            "<item>"
            f'<licensePlateNumber type="string"><![CDATA[{plate}]]></licensePlateNumber>'
            f'<groupId type="string"><![CDATA[{group_id}]]></groupId>'
            '<beginTime type="string"><![CDATA[]]></beginTime>'
            '<endTime type="string"><![CDATA[]]></endTime>'
            '<carOwner type="string"><![CDATA[]]></carOwner>'
            '<telephone type="string"><![CDATA[]]></telephone>'
            "</item>"
        )
    body = (
        f'<licensePlates type="list" total="{total}" count="{len(rows)}">'
        + "".join(items)
        + "</licensePlates>"
    )
    return xml_config(body)


def device_info_xml(api_version="2.1.0", http_post_version="2.1.0", version="2.1.0"):
    fields = ['<deviceName type="string"><![CDATA[Front Gate]]></deviceName>']
    if api_version is not None:
        fields.append(
            f'<apiVersion type="string"><![CDATA[{api_version}]]></apiVersion>'
        )
    if http_post_version is not None:
        fields.append(
            '<httpPostVersion type="string">'
            f"<![CDATA[{http_post_version}]]></httpPostVersion>"
        )
    fields.append('<model type="string"><![CDATA[IPC-MODEL]]></model>')
    return xml_config("<deviceInfo>" + "".join(fields) + "</deviceInfo>", version=version)


def device_detail_xml(api_version, http_post_version=None):
    fields = [
        f'<apiVersion type="string"><![CDATA[{api_version}]]></apiVersion>'
    ]
    if http_post_version is not None:
        fields.append(
            '<httpPostVersion type="string">'
            f"<![CDATA[{http_post_version}]]></httpPostVersion>"
        )
    body = "<detail><property>" + "".join(fields) + "</property></detail>"
    return xml_config(body)


ADD_OK = xml_config(
    "<licensePlatesReply><item>"
    '<index type="uint32">1</index>'
    '<errorCode type="uint32">0</errorCode>'
    "</item></licensePlatesReply>"
)

ADD_TOP_LEVEL_ERROR = xml_config(
    "<licensePlatesReply><item>"
    '<errorCode type="uint32">0</errorCode>'
    "</item></licensePlatesReply>",
    errorCode="1",
    errorDesc="Invalid Request",
)


class FakeResponse:
    def __init__(self, text="", status_code=200):
        self.text = text
        self.status_code = status_code


class Router:
    def __init__(self, monkeypatch):
        self.posts = []
        self.gets = []
        self.post_routes = {}
        self.get_routes = {}
        monkeypatch.setattr("viewtron.client.requests.post", self._post)
        monkeypatch.setattr("viewtron.client.requests.get", self._get)

    def _post(self, url, data=None, **kwargs):
        body = data.decode() if isinstance(data, (bytes, bytearray)) else (data or "")
        self.posts.append((url, body))
        for suffix, responder in self.post_routes.items():
            if url.endswith(suffix):
                return responder(body)
        raise AssertionError("unexpected POST " + url)

    def _get(self, url, **kwargs):
        self.gets.append(url)
        for suffix, responder in self.get_routes.items():
            if url.endswith(suffix):
                return responder()
        raise AssertionError("unexpected GET " + url)


@pytest.fixture
def camera():
    ViewtronCamera._default_group_warning_sent = False
    cam = ViewtronCamera(HOST, "admin", "password")
    yield cam
    ViewtronCamera._default_group_warning_sent = False


@pytest.fixture
def router(monkeypatch):
    return Router(monkeypatch)


def _list_plate_apis(router):
    router.post_routes["/GetSupportedAPIs"] = lambda body: FakeResponse(
        supported_xml(PLATE_API_NAMES, count=111)
    )


class TestSupportedApis:
    def test_dedup_and_count_mismatch(self, camera, router):
        _list_plate_apis(router)
        found = camera.get_supported_apis()
        assert found == frozenset({
            "GetDeviceInfo",
            "GetLicensePlates",
            "AddLicensePlates",
            "GetLicensePlateGroups",
            "ModifyLicensePlate",
            "DeleteLicensePlate",
            "GetDeviceDetail",
        })
        assert len(found) != 111
        assert 'version="2.1.0"' in router.posts[0][1]

    def test_cached_per_instance(self, camera, router):
        _list_plate_apis(router)
        assert camera.get_supported_apis() == camera.get_supported_apis()
        assert len(router.posts) == 1

    def test_http_400_returns_none(self, camera, router):
        router.post_routes["/GetSupportedAPIs"] = lambda body: FakeResponse("", 400)
        assert camera.get_supported_apis() is None
        assert camera.get_supported_apis() is None
        assert len(router.posts) == 1

    def test_error_code_1_returns_none(self, camera, router):
        router.post_routes["/GetSupportedAPIs"] = lambda body: FakeResponse(
            error_xml(1, "Invalid Request")
        )
        assert camera.get_supported_apis() is None


class TestCapabilities:
    def test_versions_and_supported_set(self, camera, router):
        _list_plate_apis(router)
        router.get_routes["/GetDeviceInfo"] = lambda: FakeResponse(device_info_xml())
        caps = camera.capabilities
        assert isinstance(caps, CameraCapabilities)
        assert caps.api_version == "2.1.0"
        assert caps.http_post_version == "2.1.0"
        assert caps.config_version == "2.1.0"
        assert "GetLicensePlates" in caps.supported_apis
        assert camera.capabilities is caps
        assert router.gets == [f"http://{HOST}/GetDeviceInfo"]

    def test_device_detail_fallback(self, camera, router):
        _list_plate_apis(router)
        router.get_routes["/GetDeviceInfo"] = lambda: FakeResponse(
            device_info_xml(api_version=None, http_post_version=None, version="2.0.0")
        )
        router.get_routes["/GetDeviceDetail"] = lambda: FakeResponse(
            device_detail_xml("2.1.0", "2.1.0")
        )
        caps = camera.capabilities
        assert caps.api_version == "2.1.0"
        assert caps.http_post_version == "2.1.0"
        assert caps.config_version == "2.0.0"
        assert any(url.endswith("/GetDeviceDetail") for url in router.gets)


class TestPlateGroups:
    def test_group_map_and_name_resolves_id(self, camera, router):
        _list_plate_apis(router)
        router.post_routes["/GetLicensePlateGroups"] = lambda body: FakeResponse(groups_xml())
        router.post_routes["/AddLicensePlates"] = lambda body: FakeResponse(ADD_OK)
        assert camera.get_plate_groups() == {
            1: "temporaryList",
            2: "whiteList",
            3: "blackList",
        }
        assert camera.add_plate("ABC1234", group="whiteList") is True
        add_bodies = [body for url, body in router.posts if url.endswith("/AddLicensePlates")]
        assert len(add_bodies) == 1
        assert "<groupId><![CDATA[2]]></groupId>" in add_bodies[0]
        assert 'version="2.1.0"' in add_bodies[0]

    def test_group_overrides_group_id_without_default_warning(self, camera, router):
        _list_plate_apis(router)
        router.post_routes["/GetLicensePlateGroups"] = lambda body: FakeResponse(groups_xml())
        router.post_routes["/AddLicensePlates"] = lambda body: FakeResponse(ADD_OK)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            camera.add_plate("ABC1234", group_id="1", group="blackList")
        assert caught == []
        add_body = [body for url, body in router.posts if url.endswith("/AddLicensePlates")][0]
        assert "<groupId><![CDATA[3]]></groupId>" in add_body


class TestPlateErrors:
    def _route_query(self, router, response):
        _list_plate_apis(router)
        router.post_routes["/GetLicensePlates"] = lambda body: response

    def test_error_20_is_empty_list(self, camera, router):
        self._route_query(router, FakeResponse(error_xml(20, "Resources Not Exist")))
        assert camera.get_plates(group_id="2") == []

    def test_error_16_raises(self, camera, router):
        self._route_query(router, FakeResponse(error_xml(16, "Range Error")))
        with pytest.raises(ViewtronAPIError) as caught:
            camera.get_plates(group_id="2")
        assert caught.value.code == "16"
        assert "Range Error" in caught.value.desc

    def test_error_1_raises_not_empty_list(self, camera, router):
        self._route_query(router, FakeResponse(error_xml(1, "Invalid Request")))
        with pytest.raises(ViewtronAPIError) as caught:
            camera.get_plates(group_id="2")
        assert caught.value.code == "1"
        assert caught.value.desc != ""

    def test_empty_body_http_400_is_typed(self, camera, router):
        self._route_query(router, FakeResponse("", 400))
        with pytest.raises(ViewtronAPIError) as caught:
            camera.get_plates(group_id="2")
        err = caught.value
        assert type(err) is ViewtronAPIError
        assert err.http_status == 400
        assert err.code == "1"
        assert err.desc == "Invalid Request (HTTP 400, empty body)"
        assert str(err) == "Invalid Request (HTTP 400, empty body)"

    def test_add_plate_checks_top_level_error_first(self, camera, router):
        _list_plate_apis(router)
        router.post_routes["/AddLicensePlates"] = lambda body: FakeResponse(ADD_TOP_LEVEL_ERROR)
        with pytest.raises(ViewtronAPIError) as caught:
            camera.add_plate("ABC1234", group_id="2")
        assert caught.value.code == "1"
        assert "Invalid Request" in str(caught.value)


class TestBackendSelection:
    def test_absent_supported_apis_uses_license_plates_when_probe_works(self, camera, router):
        router.post_routes["/GetSupportedAPIs"] = lambda body: FakeResponse("", 400)
        router.post_routes["/GetLicensePlates"] = lambda body: FakeResponse(
            plate_xml("ABC1234", "1")
        )
        plates = camera.get_plates(group_id="2")
        assert plates[0]["plate_number"] == "ABC1234"
        urls = [url for url, _body in router.posts]
        assert urls[0].endswith("/GetSupportedAPIs")
        assert all(url.endswith("/GetLicensePlates") for url in urls[1:])
        assert not any(url.endswith("/GetVehiclePlate") for url, _body in router.posts)

    def test_absent_supported_apis_and_invalid_probe_raises(self, camera, router):
        router.post_routes["/GetSupportedAPIs"] = lambda body: FakeResponse("", 400)
        router.post_routes["/GetLicensePlates"] = lambda body: FakeResponse("", 400)
        router.post_routes["/GetVehiclePlate"] = lambda body: FakeResponse("", 400)
        with pytest.raises(UnsupportedFeature, match="plate database API not available"):
            camera.get_plates()
        assert not any(url.endswith("/GetVehiclePlate") for url, _body in router.posts)

    def test_vehicle_plate_listed_without_license_plates_raises(self, camera, router):
        router.post_routes["/GetSupportedAPIs"] = lambda body: FakeResponse(
            supported_xml(["GetDeviceInfo", "GetVehiclePlate", "AddVehiclePlate"], count=3)
        )
        router.post_routes["/GetVehiclePlate"] = lambda body: FakeResponse("", 400)
        with pytest.raises(UnsupportedFeature, match="plate database API not available"):
            camera.add_plate("ABC1234", group_id="2")
        assert not any(url.endswith("/GetVehiclePlate") for url, _body in router.posts)
        assert not any(url.endswith("/AddVehiclePlate") for url, _body in router.posts)


class TestDefaultGroupWarning:
    def test_warns_once_when_default_group_is_used(self, camera, router):
        _list_plate_apis(router)
        router.post_routes["/GetLicensePlates"] = lambda body: FakeResponse(
            plate_xml("ABC1234", "1")
        )
        with pytest.warns(UserWarning, match="temporary list"):
            camera.get_plates()
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            camera.get_plates()
        assert caught == []

    def test_explicit_group_id_other_than_default_does_not_warn(self, camera, router):
        _list_plate_apis(router)
        router.post_routes["/GetLicensePlates"] = lambda body: FakeResponse(
            plate_xml("ABC1234", "2")
        )
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            plates = camera.get_plates(group_id="2")
        assert plates[0]["group_id"] == "2"
        assert caught == []


class TestGetAllPlates:
    def test_pages_with_total_across_groups(self, camera, router):
        _list_plate_apis(router)
        router.post_routes["/GetLicensePlateGroups"] = lambda body: FakeResponse(groups_xml())

        def query(body):
            if "<groupId><![CDATA[1]]></groupId>" in body:
                return FakeResponse(error_xml(20, "Resources Not Exist"))
            if "<groupId><![CDATA[2]]></groupId>" in body:
                if "<resultOffset>1</resultOffset>" in body:
                    return FakeResponse(plates_page_xml(
                        [("AAA111", "2"), ("BBB222", "2")], total=3
                    ))
                assert "<resultOffset>3</resultOffset>" in body
                return FakeResponse(plates_page_xml([("CCC333", "2")], total=3))
            if "<groupId><![CDATA[3]]></groupId>" in body:
                return FakeResponse(plates_page_xml([("DDD444", "3")], total=1))
            raise AssertionError(body)

        router.post_routes["/GetLicensePlates"] = query
        plates = camera.get_all_plates(page_size=2)
        assert [item["plate_number"] for item in plates] == [
            "AAA111", "BBB222", "CCC333", "DDD444",
        ]

    def test_named_group_does_not_scan_other_groups(self, camera, router):
        _list_plate_apis(router)
        router.post_routes["/GetLicensePlateGroups"] = lambda body: FakeResponse(groups_xml())
        seen = []

        def query(body):
            seen.append(body)
            return FakeResponse(plates_page_xml([("ABC1234", "2")], total=1))

        router.post_routes["/GetLicensePlates"] = query
        found = camera.get_all_plates(group="whiteList")
        assert [item["plate_number"] for item in found] == ["ABC1234"]
        assert len(seen) == 1
        assert "<groupId><![CDATA[2]]></groupId>" in seen[0]


MODIFY_OK = xml_config("", status="success", errorCode="0", errorDesc="No Error")


def _plate_row(plate, group_id, end_time, card=""):
    return (
        "<item>"
        f'<licensePlateNumber type="string"><![CDATA[{plate}]]></licensePlateNumber>'
        f'<groupId type="string"><![CDATA[{group_id}]]></groupId>'
        '<beginTime type="string"><![CDATA[2026-01-01 00:00:00]]></beginTime>'
        f'<endTime type="string"><![CDATA[{end_time}]]></endTime>'
        '<carOwner type="string"><![CDATA[Ada]]></carOwner>'
        '<telephone type="string"><![CDATA[555-0100]]></telephone>'
        f'<cardNumber type="string"><![CDATA[{card}]]></cardNumber>'
        "</item>"
    )


class TestVisitorPasses:
    def _routes(self, router, query):
        _list_plate_apis(router)
        router.post_routes["/GetLicensePlateGroups"] = lambda body: FakeResponse(groups_xml())
        router.post_routes["/AddLicensePlates"] = lambda body: FakeResponse(ADD_OK)
        router.post_routes["/ModifyLicensePlate"] = lambda body: FakeResponse(MODIFY_OK)
        router.post_routes["/GetLicensePlates"] = query

    def test_add_with_details_posts_add_then_modify(self, camera, router):
        self._routes(router, lambda body: FakeResponse(error_xml(20, "Resources Not Exist")))
        begin = datetime(2026, 10, 1, 8, 0, 0)
        end = datetime(2026, 10, 8, 18, 30, 0)
        with warnings.catch_warnings(record=True) as caught:
            warnings.simplefilter("always")
            assert camera.add_plate(
                "VIS1",
                group="temporary",
                owner="Ada",
                card_number="42",
                begin_time=begin,
                end_time=end,
            ) is True
        assert caught == []
        adds = [body for url, body in router.posts if url.endswith("/AddLicensePlates")]
        mods = [body for url, body in router.posts if url.endswith("/ModifyLicensePlate")]
        assert len(adds) == 1
        assert len(mods) == 1
        assert "<groupId><![CDATA[1]]></groupId>" in adds[0]
        assert "beginTime" not in adds[0]
        assert "carOwner" not in adds[0]
        assert '<carOwner type="string"><![CDATA[Ada]]></carOwner>' in mods[0]
        assert '<cardNumber type="string"><![CDATA[42]]></cardNumber>' in mods[0]
        assert '<beginTime type="string"><![CDATA[2026-10-01 08:00:00]]></beginTime>' in mods[0]
        assert '<endTime type="string"><![CDATA[2026-10-08 18:30:00]]></endTime>' in mods[0]
        assert "licensePlateType" not in mods[0]

    def test_add_without_extras_does_not_modify(self, camera, router):
        self._routes(router, lambda body: FakeResponse(error_xml(20, "Resources Not Exist")))
        assert camera.add_plate("ABC1234", group="allow") is True
        assert any(url.endswith("/AddLicensePlates") for url, _body in router.posts)
        assert not any(url.endswith("/ModifyLicensePlate") for url, _body in router.posts)
        add = [body for url, body in router.posts if url.endswith("/AddLicensePlates")][0]
        assert "<groupId><![CDATA[2]]></groupId>" in add

    def test_string_times_and_block_alias(self, camera, router):
        self._routes(router, lambda body: FakeResponse(error_xml(20, "Resources Not Exist")))
        camera.modify_plate(
            "BLK1",
            group="block",
            telephone="555-0199",
            begin_time="2026-10-01 00:00:00",
            end_time="2026-10-02",
        )
        body = [posted for url, posted in router.posts if url.endswith("/ModifyLicensePlate")][0]
        assert "<groupId><![CDATA[3]]></groupId>" in body
        assert '<telephone type="string"><![CDATA[555-0199]]></telephone>' in body
        assert '<beginTime type="string"><![CDATA[2026-10-01 00:00:00]]></beginTime>' in body
        assert '<endTime type="string"><![CDATA[2026-10-02]]></endTime>' in body

    def test_unknown_group_alias_rejected(self, camera, router):
        self._routes(router, lambda body: FakeResponse(error_xml(20, "Resources Not Exist")))
        with pytest.raises(ValueError):
            camera.add_plate("ABC1234", group="strangerList")

    def test_expiring_plates_window(self, camera, router):
        now = datetime.now().replace(microsecond=0)

        def stamp(delta):
            return (now + timedelta(days=delta)).strftime("%Y-%m-%d %H:%M:%S")

        rows = "".join([
            _plate_row("SOON", "1", stamp(1), card="7"),
            _plate_row("WEEK", "1", stamp(6), card="8"),
            _plate_row("LATER", "1", stamp(30), card="9"),
            _plate_row("PAST", "1", stamp(-1), card=""),
            _plate_row("BLANK", "1", "", card=""),
            _plate_row("BAD", "1", "not-a-date", card=""),
        ])
        body = (
            '<licensePlates type="list" total="6" count="6">'
            + rows
            + "</licensePlates>"
        )

        def query(posted):
            if "<groupId><![CDATA[1]]></groupId>" in posted:
                return FakeResponse(xml_config(body))
            return FakeResponse(error_xml(20, "Resources Not Exist"))

        self._routes(router, query)
        found = camera.get_expiring_plates(days=7)
        assert [item["plate_number"] for item in found] == ["SOON", "WEEK"]
        assert found[0]["card_number"] == "7"
        assert found[0]["owner"] == "Ada"
