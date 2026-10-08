#!/usr/bin/env python3
"""Add a temporary visitor plate and list passes expiring this week.

The camera assigns a validity window when begin and end are omitted.
This script sets both so the pass lasts a fixed number of days.
"""

from datetime import datetime, timedelta

from viewtron import ViewtronCamera

# Viewtron cameras ship set to DHCP. Use the address your router assigned.
CAMERA_IP = "192.168.1.50"
USERNAME = "admin"
PASSWORD = ""

PLATE = "IB36NL"
DAYS = 7
OWNER = "Visitor"


def main():
    camera = ViewtronCamera(CAMERA_IP, USERNAME, PASSWORD)
    begin = datetime.now().replace(microsecond=0)
    end = begin + timedelta(days=DAYS)
    camera.add_plate(
        PLATE,
        group="temporary",
        owner=OWNER,
        begin_time=begin,
        end_time=end,
    )
    print(f"Added {PLATE} on the temporary list until {end}")

    print("Passes expiring this week:")
    for plate in camera.get_expiring_plates(days=7):
        print(
            f"  {plate['plate_number']}  ends {plate['end_time']}"
            f"  owner {plate['owner']}"
        )


if __name__ == "__main__":
    main()
