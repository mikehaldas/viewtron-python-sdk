#!/usr/bin/env python3
"""
Viewtron Camera Client — test and example for the ViewtronCamera class.

Exercises all plate CRUD operations and device info against a live camera.
Uses the viewtron SDK (pip install viewtron).

Written by Mike Haldas
mike@cctvcamerapros.net
"""

from viewtron import ViewtronCamera

# ====================== CONFIG ======================
CAMERA_IP = "192.168.0.20"
USERNAME = "admin"
PASSWORD = ""

TEST_PLATE = "TEST123"
# =====================================================


def main():
    camera = ViewtronCamera(CAMERA_IP, USERNAME, PASSWORD)
    print(f"Connected to {camera}\n")

    # === Device Info ===
    print("=" * 60)
    print("DEVICE INFO")
    print("=" * 60)
    info = camera.get_device_info()
    for key, value in info.items():
        print(f"  {key}: {value}")

    # === List current plates ===
    print(f"\n{'=' * 60}")
    print("CURRENT PLATES")
    print("=" * 60)
    plates = camera.get_plates()
    if plates:
        for p in plates:
            print(f"  {p['plate_number']:<15} group={p['group_id']}  owner={p['owner']}  tel={p['telephone']}")
    else:
        print("  (none)")
    print(f"  Total: {len(plates)}")

    # === Add test plate ===
    print(f"\n{'=' * 60}")
    print(f"ADD PLATE: {TEST_PLATE}")
    print("=" * 60)
    try:
        camera.add_plate(TEST_PLATE)
        print(f"  Added {TEST_PLATE}")
    except RuntimeError as e:
        print(f"  Error: {e}")

    # === Verify it's there ===
    plates = camera.get_plates()
    found = any(p["plate_number"] == TEST_PLATE for p in plates)
    print(f"  Verify: {'FOUND' if found else 'NOT FOUND'} in database ({len(plates)} total)")

    # === Modify test plate ===
    print(f"\n{'=' * 60}")
    print(f"MODIFY PLATE: {TEST_PLATE}")
    print("=" * 60)
    try:
        camera.modify_plate(TEST_PLATE, owner="Test Owner", telephone="555-0000")
        print(f"  Modified {TEST_PLATE} — owner=Test Owner, tel=555-0000")
    except RuntimeError as e:
        print(f"  Error: {e}")

    # === Verify modification ===
    plates = camera.get_plates()
    for p in plates:
        if p["plate_number"] == TEST_PLATE:
            print(f"  Verify: owner={p['owner']}, tel={p['telephone']}")
            break

    # === Delete test plate ===
    print(f"\n{'=' * 60}")
    print(f"DELETE PLATE: {TEST_PLATE}")
    print("=" * 60)
    try:
        camera.delete_plate(TEST_PLATE)
        print(f"  Deleted {TEST_PLATE}")
    except RuntimeError as e:
        print(f"  Error: {e}")

    # === Verify deletion ===
    plates = camera.get_plates()
    found = any(p["plate_number"] == TEST_PLATE for p in plates)
    print(f"  Verify: {'STILL THERE — ERROR' if found else 'GONE'} ({len(plates)} total)")

    print(f"\n{'=' * 60}")
    print("ALL TESTS COMPLETE")
    print("=" * 60)


if __name__ == "__main__":
    main()
