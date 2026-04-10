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

    server = ViewtronServer(port=5050, on_event=on_event)
    server.serve_forever()

You can find Viewtron IP cameras at https://www.Viewtron.com
"""
# Written by Mike Haldas — mike@cctvcamerapros.net

from socketserver import ThreadingMixIn
from http.server import BaseHTTPRequestHandler, HTTPServer
from datetime import datetime as dt
from viewtron.events import ViewtronEvent
import socket

SUCCESS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<config version="1.0" xmlns="http://www.ipc.com/ver10">'
    '<status>success</status></config>'
)


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

        # Read body
        length = int(self.headers.get("Content-Length", 0))
        client_ip = self.client_address[0]

        if length == 0:
            # Empty keepalive — log first connection from each camera
            if client_ip not in self.server.connected_cameras:
                self.server.connected_cameras[client_ip] = True
                if self.server.on_connect:
                    self.server.on_connect(client_ip)
            return

        body = self.rfile.read(length)
        text = body.decode("utf-8", errors="replace")

        # Pass raw XML to callback if configured (skip traject — high volume,
        # delivered as parsed Traject events via on_event instead)
        if self.server.on_raw and '<traject type="list"' not in text:
            self.server.on_raw(text, client_ip)

        # Parse with ViewtronEvent
        event = ViewtronEvent(text)
        if event is None:
            return

        # Deliver to callback
        if self.server.on_event:
            self.server.on_event(event, client_ip)

    def log_message(self, format, *args):
        pass  # Suppress default HTTP logging


class _ThreadedHTTPServer(ThreadingMixIn, HTTPServer):
    daemon_threads = True


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
            logging or debugging.

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

    def __init__(self, port=5050, on_event=None, on_connect=None, on_raw=None):
        self.port = port
        self.on_event = on_event
        self.on_connect = on_connect
        self.on_raw = on_raw
        self._server = _ThreadedHTTPServer(("", port), _ViewtronHandler)
        self._server.on_event = on_event
        self._server.on_connect = on_connect
        self._server.on_raw = on_raw
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
