"""
Viewtron HTTP Server — receives alarm events from Viewtron IP cameras and NVRs.

Handles all the connection details that Viewtron cameras require:
HTTP/1.1 persistent connections, keepalive responses, XML success replies,
and multi-threaded request handling.

Usage:
    from viewtron import ViewtronServer

    def on_event(event, client_ip):
        print(f"[{event.category}] {event.get_alarm_type()} from {client_ip}")
        if event.category == "lpr":
            print(f"  Plate: {event.get_plate_number()}")
            print(f"  Group: {event.get_plate_group()}")

    def on_unparsed(xml, client_ip, reason):
        print(reason, client_ip)

    server = ViewtronServer(port=5050, on_event=on_event, on_unparsed=on_unparsed)
    server.serve_forever()

You can find Viewtron IP cameras at https://www.cctvcamerapros.com/viewtron-security-cameras-s/1476.htm
"""
# Written by Mike Haldas — mike@cctvcamerapros.net

from socketserver import ThreadingMixIn
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime as dt
from viewtron.events import _classify_post
import socket

SUCCESS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<config version="1.0" xmlns="http://www.ipc.com/ver10">'
    '<status>success</status></config>'
)


def _read_chunked(rfile):
    """Read an HTTP/1.1 chunked body. Does not treat it as a keepalive.

    Chunk size lines may include extensions (``size;name=value``). A zero
    chunk ends the body; trailers after it are discarded.
    """
    chunks = []
    while True:
        line = rfile.readline()
        if not line:
            break
        size_token = line.strip().split(b";", 1)[0]
        if not size_token:
            continue
        try:
            size = int(size_token, 16)
        except ValueError:
            break
        if size == 0:
            while True:
                trailer = rfile.readline()
                if trailer in (b"\r\n", b"\n", b""):
                    break
            break
        remaining = size
        data = []
        while remaining:
            part = rfile.read(remaining)
            if not part:
                break
            data.append(part)
            remaining -= len(part)
        chunks.append(b"".join(data))
        # CRLF that terminates the chunk data.
        rfile.readline()
    return b"".join(chunks)


class _ViewtronHandler(BaseHTTPRequestHandler):
    """HTTP handler for Viewtron camera events."""
    protocol_version = "HTTP/1.1"

    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-Type", "text/plain")
        self.end_headers()
        self.wfile.write(b"Viewtron event server running")

    def do_POST(self):
        # Send XML success response — this keeps the camera connection alive
        self.send_response(200)
        self.send_header("Content-Type", "application/xml")
        self.send_header("Content-Length", str(len(SUCCESS_XML)))
        self.end_headers()
        self.wfile.write(SUCCESS_XML.encode("utf-8"))

        client_ip = self.client_address[0]
        transfer = self.headers.get("Transfer-Encoding", "")
        chunked = "chunked" in transfer.lower()

        # A chunked POST has no usable Content-Length. Never treat it as
        # the empty-body keepalive, even when Content-Length is 0 or absent.
        if chunked:
            body = _read_chunked(self.rfile)
        else:
            length = int(self.headers.get("Content-Length", 0) or 0)
            if length == 0:
                # Empty keepalive — log first connection from each camera
                if client_ip not in self.server.connected_cameras:
                    self.server.connected_cameras[client_ip] = True
                    if self.server.on_connect:
                        self.server.on_connect(client_ip)
                return
            body = self.rfile.read(length)

        text = body.decode("utf-8", errors="replace")
        if not text:
            return

        # Pass raw XML to callback if configured (skip traject — high volume,
        # delivered as parsed Traject events via on_event instead)
        if self.server.on_raw and '<traject type="list"' not in text:
            self.server.on_raw(text, client_ip)

        # Parse. A malformed post should not take down the handler or the
        # camera's persistent connection.
        try:
            event, reason = _classify_post(text)
        except Exception as e:
            print(f"[{dt.now()}] Could not parse event from {client_ip}: "
                  f"{type(e).__name__}: {e}")
            if self.server.on_unparsed:
                self.server.on_unparsed(text, client_ip, "parse-error")
            return
        if event is None:
            if reason and self.server.on_unparsed:
                self.server.on_unparsed(text, client_ip, reason)
            return

        # Deliver to callback
        if self.server.on_event:
            self.server.on_event(event, client_ip)

    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True
    allow_reuse_address = True


def _get_lan_ip():
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except Exception:
        return "127.0.0.1"
    finally:
        s.close()


class ViewtronServer:
    """HTTP server that receives events from Viewtron IP cameras.

    Args:
        port: Port to listen on (default 5050)
        on_event: Callback function(event, client_ip) called for each
            parsed alarm event. event is a ViewtronEvent instance with
            .category, .get_alarm_type(), .get_plate_number(), etc.
        on_connect: Optional callback(client_ip) called when a camera
            first connects (sends its first keepalive).
        on_raw: Optional callback(xml_text, client_ip) called with the
            raw XML body of every POST (before parsing). Useful for
            logging or debugging. Traject posts are not passed here.
        on_unparsed: Optional callback(xml_text, client_ip, reason)
            called when a POST body is not a keepalive and does not
            become an event. ``reason`` is one of:

            - ``"unknown-smartType"`` — smartType is not in the table
              for that envelope (for example MOTION, or VEHICLE in a
              version-2 post that has no licensePlateListInfo)
            - ``"no-messageType"`` — a version-2 post has no
              messageType and is not an IPC-style body
            - ``"parse-error"`` — the body is not well-formed XML
            - ``"alarmStatus"`` — an alarm on/off status post

        Chunked request bodies (``Transfer-Encoding: chunked``) are
        decoded. A chunked POST is never treated as the empty-body
        keepalive, even when ``Content-Length`` is missing or 0.

    Example:
        from viewtron import ViewtronServer

        def on_event(event, client_ip):
            if event.category == "lpr":
                plate = event.get_plate_number()
                group = event.get_plate_group()
                print(f"Plate {plate} - Group: {group}")

        server = ViewtronServer(port=5050, on_event=on_event)
        server.serve_forever()
    """

    def __init__(self, port=5050, on_event=None, on_connect=None, on_raw=None,
                 on_unparsed=None):
        self.port = port
        self.on_event = on_event
        self.on_connect = on_connect
        self.on_raw = on_raw
        self.on_unparsed = on_unparsed
        self._server = _ThreadedHTTPServer(("", port), _ViewtronHandler)
        self.port = self._server.server_address[1]
        self._server.on_event = on_event
        self._server.on_connect = on_connect
        self._server.on_raw = on_raw
        self._server.on_unparsed = on_unparsed
        self._server.connected_cameras = {}

    def serve_forever(self):
        """Start the server and block until interrupted."""
        ip = _get_lan_ip()
        print(f"\nViewtron Event Server")
        print(f"Listening on http://{ip}:{self.port}")
        print(f"Ready for camera events...\n")
        try:
            self._server.serve_forever()
        except KeyboardInterrupt:
            pass
        finally:
            self._server.server_close()
            print("\nServer stopped.")

    def shutdown(self):
        """Stop the server from another thread."""
        self._server.shutdown()
