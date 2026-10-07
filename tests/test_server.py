"""Server tests for chunked posts and the on_unparsed callback."""

import io
import socket
import threading
import time

import pytest

from viewtron.server import ViewtronServer, _read_chunked


PEA_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<config version="1.7" xmlns="http://www.ipc.com/ver10">'
    '<smartType type="openAlramObj">PEA</smartType>'
    '<currentTime type="tint64">1732045234</currentTime>'
    '</config>'
)

MOTION_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<config version="1.7" xmlns="http://www.ipc.com/ver10">'
    '<smartType type="openAlramObj">MOTION</smartType>'
    '</config>'
)

NO_MESSAGE_TYPE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<config version="2.1.0" xmlns="http://www.ipc.com/ver10">'
    '<smartType>vehicle</smartType>'
    '<licensePlateListInfo><item></item></licensePlateListInfo>'
    '</config>'
)

BROKEN_XML = '<?xml version="1.0" encoding="UTF-8"?><config version="2.1.0">'

ALARM_STATUS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<config version="2.1.0" xmlns="http://www.ipc.com/ver10">'
    '<alarmStatusInfo><motionAlarm type="boolean" id="1">true</motionAlarm>'
    '</alarmStatusInfo></config>'
)

KEEPALIVE_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<config version="2.0.0" xmlns="http://www.ipc.com/ver10">'
    '<messageType>keepalive</messageType>'
    '</config>'
)


def _chunked_body(payload):
    data = payload.encode("utf-8")
    mid = max(1, len(data) // 2)
    parts = (data[:mid], data[mid:])

    def one(part):
        return f"{len(part):X}\r\n".encode() + part + b"\r\n"

    return one(parts[0]) + one(parts[1]) + b"0\r\n\r\n"


def _post(port, body, headers, timeout=2):
    sock = socket.create_connection(("127.0.0.1", port), timeout=timeout)
    try:
        sock.settimeout(timeout)
        lines = [b"POST / HTTP/1.1", b"Host: 127.0.0.1", b"Connection: close"]
        for key, value in headers:
            lines.append(f"{key}: {value}".encode())
        sock.sendall(b"\r\n".join(lines) + b"\r\n\r\n" + body)
        data = b""
        while b"\r\n\r\n" not in data:
            chunk = sock.recv(4096)
            if not chunk:
                break
            data += chunk
        return data
    finally:
        sock.close()


def _wait_until(predicate, timeout=2):
    deadline = time.time() + timeout
    while time.time() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    raise AssertionError("timed out waiting for the server callback")


@pytest.fixture
def serve():
    running = []

    def start(**callbacks):
        server = ViewtronServer(port=0, **callbacks)
        thread = threading.Thread(target=server._server.serve_forever, daemon=True)
        thread.start()
        running.append((server, thread))
        return server

    yield start
    for server, thread in running:
        server.shutdown()
        thread.join(timeout=2)
        server._server.server_close()


class TestChunkedBody:
    def test_read_chunked_joins_chunks(self):
        raw = b"4\r\nWiki\r\n5\r\npedia\r\n0\r\n\r\n"
        assert _read_chunked(io.BytesIO(raw)) == b"Wikipedia"

    def test_chunked_post_delivers_event_and_is_not_a_keepalive(self, serve):
        events = []
        connects = []
        server = serve(
            on_event=lambda event, ip: events.append(event),
            on_connect=lambda ip: connects.append(ip),
        )
        response = _post(
            server.port,
            _chunked_body(PEA_XML),
            [
                ("Transfer-Encoding", "chunked"),
                ("Content-Length", "0"),
                ("Content-Type", "application/xml"),
            ],
        )
        assert b"200" in response.split(b"\r\n", 1)[0]
        _wait_until(lambda: events)
        assert connects == []
        assert events[0].category == "intrusion"
        assert events[0].get_alarm_type() == "PEA"
        assert events[0].format == "v1"
        assert events[0].config_version == "1.7"

    def test_empty_content_length_is_still_a_keepalive(self, serve):
        events = []
        connects = []
        server = serve(
            on_event=lambda event, ip: events.append(event),
            on_connect=lambda ip: connects.append(ip),
        )
        _post(server.port, b"", [("Content-Length", "0")])
        _wait_until(lambda: connects)
        _post(server.port, b"", [("Content-Length", "0")])
        time.sleep(0.05)
        assert connects == ["127.0.0.1"]
        assert events == []


class TestOnUnparsed:
    def test_reasons_and_raw_still_fires(self, serve):
        events = []
        raw = []
        unparsed = []
        server = serve(
            on_event=lambda event, ip: events.append(event),
            on_raw=lambda xml, ip: raw.append(xml),
            on_unparsed=lambda xml, ip, reason: unparsed.append((reason, ip, xml)),
        )

        cases = [
            (MOTION_XML, "unknown-smartType"),
            (NO_MESSAGE_TYPE_XML, "no-messageType"),
            (BROKEN_XML, "parse-error"),
            (ALARM_STATUS_XML, "alarmStatus"),
        ]
        for xml, reason in cases:
            before = len(unparsed)
            body = xml.encode("utf-8")
            _post(
                server.port,
                body,
                [
                    ("Content-Length", str(len(body))),
                    ("Content-Type", "application/xml"),
                ],
            )
            _wait_until(lambda: len(unparsed) > before)
            assert unparsed[-1][0] == reason
            assert unparsed[-1][1] == "127.0.0.1"
            assert unparsed[-1][2] == xml

        assert events == []
        assert len(raw) == len(cases)

    def test_keepalive_xml_is_not_unparsed(self, serve):
        unparsed = []
        events = []
        raw = []
        server = serve(
            on_event=lambda event, ip: events.append(event),
            on_unparsed=lambda xml, ip, reason: unparsed.append(reason),
            on_raw=lambda xml, ip: raw.append(xml),
        )
        body = KEEPALIVE_XML.encode("utf-8")
        _post(
            server.port,
            body,
            [("Content-Length", str(len(body))), ("Content-Type", "application/xml")],
        )
        _wait_until(lambda: raw)
        assert unparsed == []
        assert events == []
