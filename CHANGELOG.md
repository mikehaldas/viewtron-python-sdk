# Changelog

## 1.4.0 — unreleased

Prepares the camera client and event parser for API 2.1 cameras. Outgoing
requests still use config version 2.1.0.

### Added

- **Capability discovery.** `get_supported_apis()` reads
  `applicationInterfaces/item`, de-duplicates names, and returns a
  `frozenset`. It returns `None` on Invalid Request or HTTP 400 (the command
  list is unknown, which is typical of 1.x firmware) and caches the result
  on the client. `capabilities` adds `apiVersion` and `httpPostVersion`
  from `GetDeviceInfo`, with a `GetDeviceDetail` fallback, plus the response
  config version.
- **Plate groups by name.** `get_plate_groups()` returns `{id: name}` from
  `GetLicensePlateGroups`. Plate methods take `group=` (`whiteList`,
  `blackList`, `temporaryList`) and still accept `group_id=`.
  `get_all_plates()` pages with `resultOffset`, `maxResult`, and `total`,
  and reads every group when no group is given.
- **Typed errors.** `ViewtronAPIError(code, desc, http_status)` for camera
  and HTTP failures. `UnsupportedFeature` when this firmware has no
  LicensePlates API. An empty HTTP 400 body is
  `Invalid Request (HTTP 400, empty body)`.
- **`on_unparsed(xml, client_ip, reason)`** on `ViewtronServer`. Reasons are
  `unknown-smartType`, `no-messageType`, `parse-error`, and `alarmStatus`.
  `on_raw` is unchanged.
- **`config_version` and `format`** (`"v1"` or `"v2"`) on every parsed event.

### Changed

- **Plate group id `"1"` is no longer described as the allow list.** On
  current firmware (observed on a camera running 5.3.1, API 2.1.0) group 1
  is the temporary list and the allow list is `whiteList`, typically group
  2. The `"1"` default remains for this release and warns once per process
  when a call relies on it. A future major release will default to
  `whiteList`.
- **`get_plates()` raises** on any `errorCode` other than 0 and 20. Code 20
  (Resources Not Exist) is still an empty list.
- **`add_plate()` checks the top-level error before the per-item error.**
- **`_post()` checks the HTTP status** and raises `ViewtronAPIError`.
- **Version-2 posts with no `messageType`** are parsed with the IPC classes
  when `smartType` is in the IPC table. `smartType` is matched without case
  inside a table when that does not change the class. `VEHICLE` in a
  version-2 envelope reaches `VehicleLPR` only when `licensePlateListInfo`
  is present; otherwise the post is unparsed.
- **Chunked HTTP bodies** are read by the server. A chunked POST is never
  treated as a keepalive.

The older `GetVehiclePlate` / `AddVehiclePlate` command family is not
implemented. Firmware that does not list `GetLicensePlates`, or whose
read-only `GetLicensePlates` probe returns Invalid Request, raises
`UnsupportedFeature`.

## 1.3.1 — unreleased

### Fixed

- **Crash on empty image elements.** A camera can send an image element with
  attributes but no data, such as `<sourceBase64Data type="string"><![CDATA[]]></sourceBase64Data>`.
  The parser got `None` and crashed with
  `AttributeError: 'NoneType' object has no attribute 'strip'`, and the event
  was dropped. All 11 places that read element text now go through one helper
  (`_xml_text`) that returns an empty string for a missing or empty element:
  - `CommonImagesLocation` (intrusion, zone entry/exit, loitering, illegal
    parking): source image and target image
  - `FaceDetectionImages` (IPC face detection): source image and face crop
  - `VideoMetadata` (IPC VSD): source image and target image
  - `LPR` (IPC plate recognition): overview image, plate number, plate crop,
    and the `sourceDataInfo` overview fallback
  - `APIpost`: alarm type (`smartType`)
- **No false image from an empty element.** An empty element with no
  attributes (`<sourceBase64Data/>`) used to become the literal string
  `"None"`, so `source_image_exists()` returned True and the "image" decoded
  to 3 junk bytes. It is now an empty string and reports no image.
- **`ViewtronServer` survives a bad event.** Parse errors in `do_POST` are now
  caught and logged. Before, one event that failed to parse also closed the
  camera's persistent connection, which could drop the next event.

Behavior change: a missing or empty image is now `""` (and
`source_image_exists()` / `target_image_exists()` return False) instead of a
crash or the string `"None"`. An empty plate number is now `""`.

Thanks to [@jwiemeyer](https://github.com/jwiemeyer) for the report, the
reproduction and the workaround (#1).

### Plate group API (first release that includes these changes)

These changes were merged after 1.3.0 but never published. 1.3.1 is the first
release on PyPI that includes them.

- **Added `get_plate_group()`** on `LPR` (IPC), `VehicleLPR` (NVR v2.0) and
  `APIpostV2`. It returns the raw group value from the camera or NVR, or `""`
  if the plate isn't in the database. IPC cameras use fixed values
  (`"whiteList"`, `"blackList"`, `"temporaryList"`), while NVR groups are
  user-defined names. The Viewtron Home Assistant bridge requires this method.
- **Added `get_car_owner()`** on `VehicleLPR` (NVR v2.0).
- **Removed `is_plate_authorized()`** (from `LPR`, `APIpostV2` and
  `VehicleLPR`). Use `get_plate_group()` and decide in your application what
  each group means, e.g. `event.get_plate_group() == "whiteList"`.
- **Removed `get_vehicle_list_type()`** (from `LPR`). Use `get_plate_group()`,
  which returns the same value, except `""` instead of `None` when the plate
  isn't listed.

## 1.3.0 — 2026-04-09

- `ViewtronServer`, `Traject` event class, image bytes helpers, lazy imports.
