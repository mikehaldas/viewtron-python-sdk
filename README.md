# Viewtron Python SDK

Python SDK for Viewtron IP camera API. Parse inbound alarm events and control cameras programmatically.

Viewtron IP cameras run AI detection on-camera (license plate recognition, face detection, human/vehicle detection) and send HTTP POST events to your server. This SDK parses those events and provides an API client for camera control.

Version 1.4.0 adds API 2.1 support for the [Viewtron LPR-IP4 license plate recognition camera](https://www.cctvcamerapros.com/LPR-Camera-p/lpr-ip4.htm) (firmware 5.3.x): plate direction (approach / away), confidence, allow / block / temporary plate lists by name, vehicle color, type, brand and model, capability discovery, and an `on_unparsed` hook for posts the SDK does not recognize.

## Install

```bash
pip install viewtron
```

## Inbound Events — Parse Camera Alarm Data

Viewtron cameras and NVRs send XML alarm events via HTTP POST. This SDK parses them into Python objects.

```python
from viewtron import ViewtronServer

def on_event(event, client_ip):
    if event.category == "lpr":
        print(event.get_plate_number())       # "IB36NL"
        print(event.get_plate_group())        # "whiteList" or NVR group name
        print(event.direction)                # "approach", "away", or None
        print(event.confidence)               # 0-100, e.g. 99.0
        print(event.plate_list)               # "whiteList" or None
        print(event.vehicle_color, event.vehicle_brand, event.vehicle_type)

        # Images as decoded JPEG bytes — ready for saving, MQTT, notifications
        overview = event.get_source_image_bytes()   # full scene
        plate_crop = event.get_target_image_bytes() # plate closeup

def on_unparsed(xml, client_ip, reason):
    # reason is unknown-smartType, no-messageType, parse-error, or alarmStatus
    print(reason, client_ip)

server = ViewtronServer(port=5050, on_event=on_event, on_unparsed=on_unparsed)
server.serve_forever()
```

Every parsed event has `config_version` (the post's config version, such as `"1.7"` or `"2.1.0"`) and `format` (`"v1"` or `"v2"`). A version-2 post that uses an IPC smartType and has no `messageType` is parsed with the IPC classes. `smartType` matching ignores case when that is unambiguous. `VEHICLE` in a version-2 envelope is a plate event only when `licensePlateListInfo` is present; otherwise `on_unparsed` is called with `unknown-smartType`.

`on_raw` is unchanged. The server reads `Transfer-Encoding: chunked` bodies and does not treat them as keepalives.

On an LPR event, `direction` is `"approach"`, `"away"`, or `None`. A post that says `leave` is `"away"`. `confidence` is a float from 0 to 100 (`PlateConfidence count="9900"` is `99.0`) or `None`. `plate_list` is `whiteList`, `blackList`, `temporaryList`, `strangerList`, or `None`. `vehicle_color`, `vehicle_brand`, `vehicle_type`, and `vehicle_model` come from the plate item's vehicle attributes when the post includes them. `get_plate_group()` still returns the raw group text, including a custom NVR group name. `get_time_stamp_formatted()` is the camera's event time. `currentTime` may be seconds, milliseconds, or microseconds.

`examples/gate_direction_filter.py` acts only on approaching allow-list plates at 90% confidence or higher.

Every LPR field is documented in the [license plate recognition camera API](https://videos.cctvcamerapros.com/developer/docs/applications/license-plate-recognition-camera-api/) docs. For a real driveway or HOA gate setup, see our [ALPR gate access control](https://videos.cctvcamerapros.com/v/alpr-gate-access-control.html) walkthrough.

### Supported Event Types

| Source | Class | Detection |
|--------|-------|-----------|
| IPC v1.x | `LPR` | License plate recognition with plate groups |
| IPC v1.x | `FaceDetection` | Face detection with crop image |
| IPC v1.x | `IntrusionDetection` | Perimeter intrusion (person/vehicle) |
| IPC v1.x | `IntrusionEntry` | Zone entry |
| IPC v1.x | `IntrusionExit` | Zone exit |
| IPC v1.x | `LoiteringDetection` | Loitering |
| IPC v1.x | `VideoMetadata` | Continuous object detection |
| NVR v2.0 | `VehicleLPR` | LPR with vehicle brand/color/type and plate groups |
| NVR v2.0 | `FaceDetectionV2` | Face detection with age/sex/glasses/mask |
| NVR v2.0 | `RegionIntrusion` | Perimeter intrusion |
| NVR v2.0 | `LineCrossing` | Tripwire line crossing |
| NVR v2.0 | `TargetCountingByLine` | People/vehicle counting by line |
| NVR v2.0 | `TargetCountingByArea` | People/vehicle counting by area |
| NVR v2.0 | `VideoMetadataV2` | Continuous object detection |

Version detection is automatic. IPC v1.x and version-2 posts (2.0, 2.1, and later 2.x versions with the same layout) use different XML structures; the SDK handles both. Check `event.format` and `event.config_version` when you need to tell them apart.

## Outbound API — Control the Camera

Viewtron cameras ship set to DHCP, so the camera gets its address from your router. Find it with our [IP camera finder tool](https://www.cctvcamerapros.com/IP-Camera-Network-Setup-s/1489.htm) and use it in place of the example address below.

```python
from viewtron import ViewtronCamera

camera = ViewtronCamera("192.168.0.20", "admin", "password")

# Device info
info = camera.get_device_info()
print(info["model"])  # "LPR-IP4"

# What this firmware supports
caps = camera.capabilities
print(caps.api_version, caps.http_post_version, caps.config_version)
print(caps.supported_apis)  # frozenset, or None when GetSupportedAPIs is unavailable

# Plate groups. On current firmware (a camera running 5.3.1, API 2.1.0)
# group 1 is temporaryList and the allow list is whiteList, typically group 2.
print(camera.get_plate_groups())  # {1: "temporaryList", 2: "whiteList", 3: "blackList"}

# Manage the license plate database. Pass group= so the id is resolved for you.
# Omitting it still uses group id "1" and warns once; that default changes in a future major release.
plates = camera.get_plates(group="whiteList")
camera.add_plate("IB36NL", group="allow")  # allow, block, and temporary also resolve
camera.modify_plate("IB36NL", owner="Mike", telephone="555-1234", group="whiteList")
camera.delete_plate("IB36NL", group="whiteList")
all_plates = camera.get_all_plates()  # every group, paged with resultOffset / maxResult / total

# Temporary visitor pass. Omitting begin_time and end_time lets the camera
# assign the validity window. Pass both when the pass should last N days.
from datetime import datetime, timedelta
start = datetime.now().replace(microsecond=0)
camera.add_plate(
    "IB36NL",
    group="temporary",
    owner="Visitor",
    card_number="1001",
    begin_time=start,
    end_time=start + timedelta(days=7),
)
this_week = camera.get_expiring_plates(days=7)

# Or use as context manager
with ViewtronCamera("192.168.0.20", "admin", "password") as cam:
    plates = cam.get_plates(group="whiteList")
```

## Projects Using This SDK

- **[Viewtron Home Assistant Integration](https://github.com/mikehaldas/viewtron-home-assistant)** — Camera events as HA sensors via MQTT auto-discovery
- **[Viewtron Node.js SDK](https://github.com/mikehaldas/viewtron-nodejs-sdk)** — The same camera events for Node.js (`npm install viewtron-sdk`)
- **[Node-RED Viewtron node](https://github.com/mikehaldas/node-red-contrib-viewtron)** — License plate, intrusion, face and counting events in Node-RED flows
- **[IP Camera API Server](https://github.com/mikehaldas/IP-Camera-API)** — Alarm server with CSV logging and image saving

## Documentation

- **[API Developer Docs](https://videos.cctvcamerapros.com/developer/)** — Full Viewtron API documentation portal
- **[Python SDK Reference](https://videos.cctvcamerapros.com/developer/docs/getting-started/python-sdk/)** — Event classes, camera client, version routing
- **[Home Assistant Integration](https://videos.cctvcamerapros.com/developer/docs/integrations/home-assistant/)** — Connect cameras to HA via MQTT
- [XML Event Examples](https://github.com/mikehaldas/IP-Camera-API/tree/main/examples)
- `examples/visitor_pass.py` — add a temporary pass and list plates expiring this week
- `examples/gate_direction_filter.py` — approaching allow-list plates at 90% confidence or higher
- [IP Camera Setup Guide](https://videos.cctvcamerapros.com/support/topic/ip-camera-api-webbooks)
- [NVR Setup Guide](https://videos.cctvcamerapros.com/support/topic/setup-nvr-api-webhooks)
- [LPR camera API guide](https://videos.cctvcamerapros.com/v/lpr-camera-api.html) — plate webhooks, this SDK and Home Assistant, step by step
- [Home Assistant license plate recognition](https://videos.cctvcamerapros.com/support/topic/home-assistant-lpr-camera-api) — forum walkthrough with automations
- [Viewtron LPR camera API / HTTP Post questions](https://videos.cctvcamerapros.com/support/topic/lpr-camera-api-http-post) — answers to common integration questions

## Products

- [Viewtron security cameras and surveillance systems](https://www.cctvcamerapros.com/viewtron-security-cameras-s/1476.htm)
- [Viewtron license plate recognition systems](https://www.cctvcamerapros.com/License-Plate-Recognition-Systems-s/1518.htm)
- [Viewtron IP cameras](https://www.cctvcamerapros.com/viewtron-IP-cameras-s/1474.htm) and [IP camera NVRs](https://www.cctvcamerapros.com/IP-Camera-NVRs-s/1472.htm)
- [AI security cameras](https://www.cctvcamerapros.com/AI-security-cameras-s/1512.htm)

## Author

Mike Haldas — [CCTV Camera Pros](https://www.cctvcamerapros.com)
mike@cctvcamerapros.net
