#!/usr/bin/env python3
"""Act only on approaching allow-list plates at 90% confidence or higher.

``direction`` is ``approach`` or ``away``. ``confidence`` is 0–100.
``plate_list`` is ``whiteList`` for the allow list.
"""

from viewtron import ViewtronServer


def on_event(event, client_ip):
    if event.category != "lpr":
        return
    if event.direction != "approach":
        return
    if event.confidence is None or event.confidence < 90:
        return
    if event.plate_list != "whiteList":
        return
    print(
        f"open gate for {event.get_plate_number()} "
        f"({event.confidence:.2f}%) from {client_ip}"
    )


def main():
    server = ViewtronServer(port=5050, on_event=on_event)
    server.serve_forever()


if __name__ == "__main__":
    main()
