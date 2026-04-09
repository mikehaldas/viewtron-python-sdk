# Viewtron Python SDK

Python SDK for Viewtron IP camera API. Parse inbound alarm events and control cameras programmatically.

Viewtron IP cameras run AI detection on-camera (license plate recognition, face detection, human/vehicle detection) and send HTTP POST events to your server. This SDK parses those events and provides an API client for camera control.

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
        print(event.get_plate_number())       # "ABC1234"
        print(event.get_plate_group())        # "whiteList" or NVR group name

        # Images as decoded JPEG bytes — ready for saving, MQTT, notifications
        overview = event.get_source_image_bytes()   # full scene
        plate_crop = event.get_target_image_bytes() # plate closeup

server = ViewtronServer(port=5050, on_event=on_event)
server.serve_forever()
```

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

Version detection is automatic — IPC v1.x and NVR v2.0 use different XML structures but the SDK handles both.

## Outbound API — Control the Camera

```python
from viewtron import ViewtronCamera

camera = ViewtronCamera("192.168.0.20", "admin", "password")

# Device info
info = camera.get_device_info()
print(info["model"])  # "LPR-IP4"

# Manage the license plate database
plates = camera.get_plates()
camera.add_plate("ABC1234")
camera.modify_plate("ABC1234", owner="Mike", telephone="555-1234")
camera.delete_plate("ABC1234")

# Or use as context manager
with ViewtronCamera("192.168.0.20", "admin", "password") as cam:
    plates = cam.get_plates()
```

## Projects Using This SDK

- **[Viewtron Home Assistant Integration](https://github.com/mikehaldas/viewtron-homeassistant)** — Camera events as HA sensors via MQTT auto-discovery
- **[IP Camera API Server](https://github.com/mikehaldas/IP-Camera-API)** — Alarm server with CSV logging and image saving

## Documentation

- **[API Developer Docs](https://videos.cctvcamerapros.com/developer/)** — Full Viewtron API documentation portal
- **[Python SDK Reference](https://videos.cctvcamerapros.com/developer/docs/getting-started/python-sdk/)** — Event classes, camera client, version routing
- **[Home Assistant Integration](https://videos.cctvcamerapros.com/developer/docs/integrations/home-assistant/)** — Connect cameras to HA via MQTT
- [XML Event Examples](https://github.com/mikehaldas/IP-Camera-API/tree/main/examples)
- [IP Camera Setup Guide](https://videos.cctvcamerapros.com/support/topic/ip-camera-api-webbooks)
- [NVR Setup Guide](https://videos.cctvcamerapros.com/support/topic/setup-nvr-api-webhooks)

## Products

- [All Viewtron Products](https://www.Viewtron.com)
- [AI Security Cameras](https://www.cctvcamerapros.com/AI-security-cameras-s/1512.htm)
- [LPR Cameras](https://www.cctvcamerapros.com/License-Plate-Recognition-Systems-s/1518.htm)
- [Face Recognition Cameras](https://www.cctvcamerapros.com/face-recognition-cameras-s/1761.htm)

## Author

Mike Haldas — [CCTV Camera Pros](https://www.cctvcamerapros.com)
mike@cctvcamerapros.net
