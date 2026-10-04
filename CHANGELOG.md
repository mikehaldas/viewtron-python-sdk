# Changelog

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
