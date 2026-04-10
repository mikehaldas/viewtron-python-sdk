# Table of Contents

* [viewtron.events](#viewtron.events)
  * [APIpost](#viewtron.events.APIpost)
    * [get\_alarm\_description](#viewtron.events.APIpost.get_alarm_description)
    * [get\_target\_types](#viewtron.events.APIpost.get_target_types)
    * [get\_time\_stamp\_formatted](#viewtron.events.APIpost.get_time_stamp_formatted)
    * [get\_time\_stamp](#viewtron.events.APIpost.get_time_stamp)
    * [get\_ip\_cam](#viewtron.events.APIpost.get_ip_cam)
    * [get\_alarm\_type](#viewtron.events.APIpost.get_alarm_type)
    * [get\_plate\_number](#viewtron.events.APIpost.get_plate_number)
    * [source\_image\_exists](#viewtron.events.APIpost.source_image_exists)
    * [target\_image\_exists](#viewtron.events.APIpost.target_image_exists)
    * [images\_exist](#viewtron.events.APIpost.images_exist)
    * [get\_source\_image](#viewtron.events.APIpost.get_source_image)
    * [get\_target\_image](#viewtron.events.APIpost.get_target_image)
    * [get\_source\_image\_bytes](#viewtron.events.APIpost.get_source_image_bytes)
    * [get\_target\_image\_bytes](#viewtron.events.APIpost.get_target_image_bytes)
  * [FaceDetectionImages](#viewtron.events.FaceDetectionImages)
  * [LPR](#viewtron.events.LPR)
    * [get\_plate\_group](#viewtron.events.LPR.get_plate_group)
  * [APIpostV2](#viewtron.events.APIpostV2)
    * [get\_source\_image\_bytes](#viewtron.events.APIpostV2.get_source_image_bytes)
    * [get\_target\_image\_bytes](#viewtron.events.APIpostV2.get_target_image_bytes)
  * [VehicleLPR](#viewtron.events.VehicleLPR)
    * [get\_plate\_number](#viewtron.events.VehicleLPR.get_plate_number)
    * [get\_plate\_color](#viewtron.events.VehicleLPR.get_plate_color)
    * [get\_car\_type](#viewtron.events.VehicleLPR.get_car_type)
    * [get\_car\_color](#viewtron.events.VehicleLPR.get_car_color)
    * [get\_car\_brand](#viewtron.events.VehicleLPR.get_car_brand)
    * [get\_car\_model](#viewtron.events.VehicleLPR.get_car_model)
    * [get\_plate\_group](#viewtron.events.VehicleLPR.get_plate_group)
    * [get\_car\_owner](#viewtron.events.VehicleLPR.get_car_owner)
  * [FaceDetectionV2](#viewtron.events.FaceDetectionV2)
    * [get\_face\_age](#viewtron.events.FaceDetectionV2.get_face_age)
    * [get\_face\_sex](#viewtron.events.FaceDetectionV2.get_face_sex)
    * [get\_face\_glasses](#viewtron.events.FaceDetectionV2.get_face_glasses)
    * [get\_face\_mask](#viewtron.events.FaceDetectionV2.get_face_mask)
  * [Traject](#viewtron.events.Traject)
  * [ViewtronEvent](#viewtron.events.ViewtronEvent)

<a id="viewtron.events"></a>

# viewtron.events

Viewtron Event Parser — transforms camera HTTP POST XML into Python objects.

Viewtron IP cameras send HTTP POST requests containing XML data when AI
detection events occur (license plate recognition, intrusion detection,
face detection, etc.). This module parses that XML into structured Python
objects with a consistent interface.

Most developers should use ``ViewtronEvent`` (the factory function) or
``ViewtronServer`` rather than instantiating event classes directly.

**Example**:

  from viewtron import ViewtronEvent
  
  event = ViewtronEvent(xml_body)
  if event and event.category == "lpr":
  print(event.get_plate_number())
  print(event.get_plate_group())
  
  You can find Viewtron IP cameras at https://www.Viewtron.com

<a id="viewtron.events.APIpost"></a>

## APIpost Objects

```python
class APIpost()
```

Base class for IPC v1.x camera events.

Parses common fields shared by all event types: device name, alarm type,
timestamp, and images. Subclasses add event-specific fields (plate number,
face attributes, etc.).

**Attributes**:

- `category` _str_ - Event category set by ViewtronEvent — "lpr", "face",
  "intrusion", "counting", "metadata", or "traject".
- `alarm_type` _str_ - Raw alarm type from the camera XML (e.g., "VEHICE",
  "VFD", "PEA").
- `alarm_description` _str_ - Human-readable description (e.g.,
  "License Plate Detection").
- `ip_cam` _str_ - Camera device name.
  

**Notes**:

  Do not instantiate directly. Use ``ViewtronEvent(xml)`` instead.

<a id="viewtron.events.APIpost.get_alarm_description"></a>

#### get\_alarm\_description

```python
def get_alarm_description()
```

Returns human-readable event description (e.g., "License Plate Detection").

<a id="viewtron.events.APIpost.get_target_types"></a>

#### get\_target\_types

```python
def get_target_types()
```

Returns supported target types from the camera (person, car, motor).

<a id="viewtron.events.APIpost.get_time_stamp_formatted"></a>

#### get\_time\_stamp\_formatted

```python
def get_time_stamp_formatted()
```

Returns event timestamp as a formatted string.

**Returns**:

- `str` - Timestamp like "2026-04-09 15:30:45".

<a id="viewtron.events.APIpost.get_time_stamp"></a>

#### get\_time\_stamp

```python
def get_time_stamp()
```

Returns current Unix timestamp as a string (used for filenames).

**Returns**:

- `str` - Unix timestamp like "1775748316".

<a id="viewtron.events.APIpost.get_ip_cam"></a>

#### get\_ip\_cam

```python
def get_ip_cam()
```

Returns the camera's device name.

**Returns**:

- `str` - Device name (e.g., "Viewtron IPC").

<a id="viewtron.events.APIpost.get_alarm_type"></a>

#### get\_alarm\_type

```python
def get_alarm_type()
```

Returns the raw alarm type code from the camera XML.

**Returns**:

- `str` - Alarm type (e.g., "VEHICE", "VFD", "PEA", "vehicle").

<a id="viewtron.events.APIpost.get_plate_number"></a>

#### get\_plate\_number

```python
def get_plate_number()
```

Returns the detected license plate number.

**Returns**:

- `str` - Plate number (e.g., "ABC1234") or "<NO PLATE EXISTS>"
  if this is not an LPR event.

<a id="viewtron.events.APIpost.source_image_exists"></a>

#### source\_image\_exists

```python
def source_image_exists()
```

Returns True if the event contains an overview/scene image.

**Returns**:

- `bool` - True if a base64-encoded overview image is available.

<a id="viewtron.events.APIpost.target_image_exists"></a>

#### target\_image\_exists

```python
def target_image_exists()
```

Returns True if the event contains a target crop image.

**Returns**:

- `bool` - True if a base64-encoded target image is available
  (plate crop for LPR, face crop for face detection).

<a id="viewtron.events.APIpost.images_exist"></a>

#### images\_exist

```python
def images_exist()
```

Returns True if the event contains any images.

**Returns**:

- `bool` - True if either overview or target image is available.

<a id="viewtron.events.APIpost.get_source_image"></a>

#### get\_source\_image

```python
def get_source_image()
```

Returns the overview/scene image as a base64-encoded string.

**Returns**:

  str or None: Base64 JPEG data, or None if no image.

<a id="viewtron.events.APIpost.get_target_image"></a>

#### get\_target\_image

```python
def get_target_image()
```

Returns the target crop image as a base64-encoded string.

**Returns**:

  str or None: Base64 JPEG data (plate crop, face crop, etc.),
  or None if no image.

<a id="viewtron.events.APIpost.get_source_image_bytes"></a>

#### get\_source\_image\_bytes

```python
def get_source_image_bytes()
```

Returns the overview/scene image as decoded JPEG bytes.

Ready to save to disk, publish to MQTT, or include in notifications.

**Returns**:

  bytes or None: JPEG image data, or None if no image.

<a id="viewtron.events.APIpost.get_target_image_bytes"></a>

#### get\_target\_image\_bytes

```python
def get_target_image_bytes()
```

Returns the target crop image as decoded JPEG bytes.

Ready to save to disk, publish to MQTT, or include in notifications.
For LPR events this is the plate crop, for face detection it's the
face crop.

**Returns**:

  bytes or None: JPEG image data, or None if no image.

<a id="viewtron.events.FaceDetectionImages"></a>

## FaceDetectionImages Objects

```python
class FaceDetectionImages(APIpost)
```

Dedicated image extractor for Face Detection (VFD + FEATURE_RESULT) events.
Replaces CommonImagesLocation for FaceDetection – images are delivered differently:
  • Full scene image  → in <sourceDataInfo><sourceBase64Data>
  • Face crop(s)      → in each <item><targetImageData><targetBase64Data>

<a id="viewtron.events.LPR"></a>

## LPR Objects

```python
class LPR(APIpost)
```

IPC v1.x License Plate Recognition event (smartType: VEHICE/VEHICLE).

Parses plate number, authorization status, and images from the camera's
HTTP POST XML.

**Attributes**:

- `plate_number` _str_ - Detected plate text (e.g., "ABC1234").
- `vehicleListType` _str or None_ - "whiteList", "blackList",
  "temporaryList", or None if the plate is not in the database.
  

**Example**:

  event = ViewtronEvent(xml_body)
  if event.category == "lpr":
  print(event.get_plate_number())  # "ABC1234"
  print(event.get_plate_group())   # "whiteList"

<a id="viewtron.events.LPR.get_plate_group"></a>

#### get\_plate\_group

```python
def get_plate_group()
```

Returns the plate's database group from the IPC camera.

The IPC camera uses fixed group names in the XML vehicleListType field.
The application decides what each group means.

**Returns**:

- `str` - Plate group — "whiteList", "blackList", "temporaryList",
  or empty string if the plate is not in the camera's database.
  
  IPC camera group values (raw XML values, not UI labels):
  - "whiteList" — camera UI shows this as "Allow list"
  - "blackList" — camera UI shows this as "Block list"
  - "temporaryList" — camera UI shows this as "Temporary vehicle"
  - "" (empty) — plate is not in the database, or temporary plate
  with an expired date range

<a id="viewtron.events.APIpostV2"></a>

## APIpostV2 Objects

```python
class APIpostV2()
```

Base class for NVR v2.0 HTTP Posts.

<a id="viewtron.events.APIpostV2.get_source_image_bytes"></a>

#### get\_source\_image\_bytes

```python
def get_source_image_bytes()
```

Returns the overview/scene image as decoded JPEG bytes.

**Returns**:

  bytes or None: JPEG image data, or None if no image.

<a id="viewtron.events.APIpostV2.get_target_image_bytes"></a>

#### get\_target\_image\_bytes

```python
def get_target_image_bytes()
```

Returns the target crop image as decoded JPEG bytes.

**Returns**:

  bytes or None: JPEG image data, or None if no image.

<a id="viewtron.events.VehicleLPR"></a>

## VehicleLPR Objects

```python
class VehicleLPR(APIpostV2)
```

NVR v2.0 License Plate Recognition (smartType: vehicle).

Uses a completely different XML structure from other v2.0 alarm types:
- licensePlateListInfo instead of eventInfo + targetListInfo
- Plate number in licensePlateAttribute/licensePlateNumber
- Vehicle attributes: carType, color, brand, model
- Plate database match in licensePlateMatchInfo (groupName, carOwner, etc.)
- Target image is a plate crop inside licensePlateListInfo/item/targetImageData

**Attributes**:

- `group_name` _str_ - NVR plate group name (e.g., "Whitelist", "Residents").
  Empty string if the plate is not in the NVR database.
  NVR groups are user-defined — unlike IPC cameras which use fixed
  whiteList/blackList/temporaryList values.
- `car_owner` _str_ - Owner name from the NVR plate database.

<a id="viewtron.events.VehicleLPR.get_plate_number"></a>

#### get\_plate\_number

```python
def get_plate_number()
```

Returns the detected license plate number.

**Returns**:

- `str` - Plate number (e.g., "ABC1234") or "<NO PLATE>".

<a id="viewtron.events.VehicleLPR.get_plate_color"></a>

#### get\_plate\_color

```python
def get_plate_color()
```

Returns the detected plate color (e.g., "blue", "yellow").

**Returns**:

- `str` - Plate color, or empty string if not detected.

<a id="viewtron.events.VehicleLPR.get_car_type"></a>

#### get\_car\_type

```python
def get_car_type()
```

Returns the detected vehicle type (e.g., "sedan", "SUV", "truck").

**Returns**:

- `str` - Vehicle type, or empty string if not detected.

<a id="viewtron.events.VehicleLPR.get_car_color"></a>

#### get\_car\_color

```python
def get_car_color()
```

Returns the detected vehicle color.

**Returns**:

- `str` - Vehicle color, or empty string if not detected.

<a id="viewtron.events.VehicleLPR.get_car_brand"></a>

#### get\_car\_brand

```python
def get_car_brand()
```

Returns the detected vehicle brand (e.g., "Toyota", "Ford").

**Returns**:

- `str` - Vehicle brand, or empty string if not detected.

<a id="viewtron.events.VehicleLPR.get_car_model"></a>

#### get\_car\_model

```python
def get_car_model()
```

Returns the detected vehicle model.

**Returns**:

- `str` - Vehicle model, or empty string if not detected.

<a id="viewtron.events.VehicleLPR.get_plate_group"></a>

#### get\_plate\_group

```python
def get_plate_group()
```

Returns the plate's database group from the NVR.

NVR plate groups are user-defined — you create groups and name them
whatever you want (e.g., "Whitelist", "Residents", "Banned").
The application decides what each group means.

**Returns**:

- `str` - Group name, or empty string if the plate is not in the
  NVR database.

<a id="viewtron.events.VehicleLPR.get_car_owner"></a>

#### get\_car\_owner

```python
def get_car_owner()
```

Returns the owner name from the NVR plate database.

**Returns**:

- `str` - Owner name, or empty string if not set.

<a id="viewtron.events.FaceDetectionV2"></a>

## FaceDetectionV2 Objects

```python
class FaceDetectionV2(APIpostV2)
```

NVR v2.0 Face Detection (smartType: videoFaceDetect).

Uses faceListInfo instead of eventInfo + targetListInfo.
Each face item includes attributes: age, sex, glasses, mask.
Target image is a square face crop inside faceListInfo/item/targetImageData.

<a id="viewtron.events.FaceDetectionV2.get_face_age"></a>

#### get\_face\_age

```python
def get_face_age()
```

Returns estimated age of the detected face.

**Returns**:

- `str` - Age estimate (e.g., "25"), or empty string.

<a id="viewtron.events.FaceDetectionV2.get_face_sex"></a>

#### get\_face\_sex

```python
def get_face_sex()
```

Returns estimated sex of the detected face.

**Returns**:

- `str` - "male" or "female", or empty string.

<a id="viewtron.events.FaceDetectionV2.get_face_glasses"></a>

#### get\_face\_glasses

```python
def get_face_glasses()
```

Returns whether the detected face is wearing glasses.

**Returns**:

- `str` - "yes" or "no", or empty string.

<a id="viewtron.events.FaceDetectionV2.get_face_mask"></a>

#### get\_face\_mask

```python
def get_face_mask()
```

Returns whether the detected face is wearing a mask.

**Returns**:

- `str` - "yes" or "no", or empty string.

<a id="viewtron.events.Traject"></a>

## Traject Objects

```python
class Traject()
```

Parsed traject (smart tracking) event from a Viewtron camera.

Traject posts are high-volume — cameras send them multiple times per second
for each tracked target. Each post contains target ID, type (person/car/motor),
bounding box, velocity, and direction.

**Attributes**:

- `category` - Always "traject"
- `targets` - List of dicts with keys: target_id, target_type, rect, velocity, direction
- `device_name` - Camera name from the post
- `mac` - Camera MAC address
- `timestamp` - Event timestamp

<a id="viewtron.events.ViewtronEvent"></a>

#### ViewtronEvent

```python
def ViewtronEvent(post_body)
```

Parse any HTTP POST body from a Viewtron camera or NVR.

Single entry point for the SDK. Takes the raw XML string from a camera's
HTTP POST, detects the API version and event type, and returns the
correct parsed event object.

**Arguments**:

- `post_body` _str_ - Raw XML string from the camera's HTTP POST body.
  

**Returns**:

  Event object with a ``.category`` attribute, or None.
  
  Possible categories and their event classes:
  
  - ``"lpr"`` — LPR (v1.x) or VehicleLPR (v2.0). Plate number,
  authorization status, vehicle attributes, images.
  - ``"face"`` — FaceDetection (v1.x) or FaceDetectionV2 (v2.0).
  Age, sex, glasses, mask attributes.
  - ``"intrusion"`` — IntrusionDetection, IntrusionEntry,
  IntrusionExit, RegionIntrusion, LineCrossing.
  - ``"counting"`` — TargetCountingByLine, TargetCountingByArea.
  - ``"metadata"`` — VideoMetadata (v1.x) or VideoMetadataV2 (v2.0).
  - ``"traject"`` — Traject. High-volume tracking data with target
  IDs, types, and bounding boxes.
  - None — Keepalives, alarm status messages, unrecognized events.
  

**Example**:

  from viewtron import ViewtronEvent
  
  event = ViewtronEvent(xml_body)
  if event is None:
  return  # keepalive or unrecognized
  
  print(event.category)               # "lpr"
  print(event.get_alarm_type())       # "VEHICE"
  print(event.get_alarm_description()) # "License Plate Detection"
  
  if event.category == "lpr":
  print(event.get_plate_number())      # "ABC1234"
  print(event.get_plate_group())       # "whiteList"

