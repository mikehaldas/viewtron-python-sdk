#!/usr/bin/env python3
"""Live test for ViewtronEvent — point your camera's HTTP POST at this server."""

from http.server import BaseHTTPRequestHandler, HTTPServer
from viewtron import ViewtronEvent

PORT = 5050

SUCCESS_XML = (
    '<?xml version="1.0" encoding="UTF-8"?>'
    '<config version="1.0" xmlns="http://www.ipc.com/ver10">'
    '<status>success</status></config>'
)

class Handler(BaseHTTPRequestHandler):
    def do_POST(self):
        self.send_response(200)
        self.send_header('Content-Type', 'application/xml')
        self.send_header('Content-Length', str(len(SUCCESS_XML)))
        self.end_headers()
        self.wfile.write(SUCCESS_XML.encode())

        length = int(self.headers.get('Content-Length', 0))
        if length == 0:
            return
        body = self.rfile.read(length).decode('utf-8', errors='replace')

        event = ViewtronEvent(body)
        if event is None:
            print("  [skip] keepalive / status / unrecognized")
            return

        print(f"\n{'='*60}")
        print(f"  Category:    {event.category}")
        print(f"  Alarm Type:  {event.get_alarm_type()}")
        print(f"  Description: {event.get_alarm_description()}")
        print(f"  Camera:      {event.get_ip_cam()}")
        print(f"  Timestamp:   {event.get_time_stamp_formatted()}")
        print(f"  Images:      source={event.source_image_exists()}, target={event.target_image_exists()}")

        if event.category == "lpr":
            print(f"  Plate:       {event.get_plate_number()}")
            print(f"  Authorized:  {event.is_plate_authorized()}")
            if hasattr(event, 'vehicleListType'):
                print(f"  List Type:   {event.get_vehicle_list_type()}")
            if hasattr(event, 'car_brand') and event.car_brand:
                print(f"  Vehicle:     {event.get_car_brand()} {event.get_car_model()} ({event.get_car_type()}, {event.get_car_color()})")

        elif event.category == "face":
            if hasattr(event, 'face_age'):
                print(f"  Face:        age={event.get_face_age()}, sex={event.get_face_sex()}, glasses={event.get_face_glasses()}, mask={event.get_face_mask()}")

        elif event.category == "intrusion":
            print(f"  Event type:  {event.get_alarm_description()}")

    def do_GET(self):
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"ViewtronEvent live test running")

    def log_message(self, format, *args):
        pass

if __name__ == '__main__':
    print(f"ViewtronEvent live test server on port {PORT}")
    print(f"Point your camera HTTP POST to this machine's IP:{PORT}")
    print(f"Waiting for events...\n")
    HTTPServer(('', PORT), Handler).serve_forever()
