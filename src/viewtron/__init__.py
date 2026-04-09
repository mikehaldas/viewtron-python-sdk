"""
Viewtron IP Camera Python SDK

Parse inbound alarm events from Viewtron IP cameras and NVRs,
and control cameras via the outbound API.

Inbound events (camera sends HTTP POST to your server):
    from viewtron import ViewtronServer, ViewtronEvent

Outbound API (your app sends commands to the camera):
    from viewtron import ViewtronCamera

Full documentation: https://github.com/mikehaldas/viewtron-python
Product page: https://www.Viewtron.com
"""


def __getattr__(name):
    """Lazy imports — only load modules when their classes are accessed."""

    # Event classes and factory (events.py)
    _events = {
        "APIpost", "LPR", "FaceDetection", "IntrusionDetection",
        "IntrusionEntry", "IntrusionExit", "LoiteringDetection",
        "IllegalParking", "VideoMetadata", "CommonImagesLocation",
        "FaceDetectionImages", "VT_alarm_types",
        "APIpostV2", "VehicleLPR", "FaceDetectionV2", "RegionIntrusion",
        "LineCrossing", "TargetCountingByLine", "TargetCountingByArea",
        "VideoMetadataV2", "VT_alarm_types_v2",
        "Traject", "ViewtronEvent",
    }
    if name in _events:
        from viewtron import events
        return getattr(events, name)

    # Camera client (client.py)
    if name == "ViewtronCamera":
        from viewtron.client import ViewtronCamera
        return ViewtronCamera

    # Event server (server.py)
    if name == "ViewtronServer":
        from viewtron.server import ViewtronServer
        return ViewtronServer

    raise AttributeError(f"module 'viewtron' has no attribute {name!r}")


__version__ = "1.2.0"

__all__ = [
    # IPC v1.x
    "APIpost",
    "LPR",
    "FaceDetection",
    "IntrusionDetection",
    "IntrusionEntry",
    "IntrusionExit",
    "LoiteringDetection",
    "IllegalParking",
    "VideoMetadata",
    "CommonImagesLocation",
    "FaceDetectionImages",
    "VT_alarm_types",
    # NVR v2.0
    "APIpostV2",
    "VehicleLPR",
    "FaceDetectionV2",
    "RegionIntrusion",
    "LineCrossing",
    "TargetCountingByLine",
    "TargetCountingByArea",
    "VideoMetadataV2",
    "VT_alarm_types_v2",
    # Event factory
    "ViewtronEvent",
    # Traject
    "Traject",
    # Client
    "ViewtronCamera",
    # Server
    "ViewtronServer",
]
