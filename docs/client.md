# Table of Contents

* [viewtron.client](#viewtron.client)
  * [ViewtronAPIError](#viewtron.client.ViewtronAPIError)
  * [UnsupportedFeature](#viewtron.client.UnsupportedFeature)
  * [CameraCapabilities](#viewtron.client.CameraCapabilities)
  * [ViewtronCamera](#viewtron.client.ViewtronCamera)
    * [get\_device\_info](#viewtron.client.ViewtronCamera.get_device_info)
    * [get\_supported\_apis](#viewtron.client.ViewtronCamera.get_supported_apis)
    * [capabilities](#viewtron.client.ViewtronCamera.capabilities)
    * [get\_plate\_groups](#viewtron.client.ViewtronCamera.get_plate_groups)
    * [add\_plate](#viewtron.client.ViewtronCamera.add_plate)
    * [add\_plates](#viewtron.client.ViewtronCamera.add_plates)
    * [get\_plates](#viewtron.client.ViewtronCamera.get_plates)
    * [get\_all\_plates](#viewtron.client.ViewtronCamera.get_all_plates)
    * [modify\_plate](#viewtron.client.ViewtronCamera.modify_plate)
    * [delete\_plate](#viewtron.client.ViewtronCamera.delete_plate)

<a id="viewtron.client"></a>

# viewtron.client

Viewtron Camera Client — send commands to cameras and manage plate databases.

Uses Basic HTTP authentication to communicate with Viewtron IP cameras.
Supports license plate CRUD operations and device info queries.

**Example**:

  from viewtron import ViewtronCamera
  
  camera = ViewtronCamera("192.168.0.20", "admin", "password")
  
  # Plate management
  camera.add_plate("ABC1234", group="whiteList")
  plates = camera.get_plates(group="whiteList")
  camera.modify_plate("ABC1234", owner="Mike", telephone="555-1234", group="whiteList")
  camera.delete_plate("ABC1234", group="whiteList")
  
  # Device info
  info = camera.get_device_info()

<a id="viewtron.client.ViewtronAPIError"></a>

## ViewtronAPIError Objects

```python
class ViewtronAPIError(RuntimeError)
```

The camera rejected a command or returned an HTTP error.

Subclasses ``RuntimeError`` so existing ``except RuntimeError`` handlers
still catch API failures.

**Attributes**:

- `code` - Device ``errorCode`` as a string, when the camera sent one.
- `desc` - Short description. For an empty HTTP 400 body this is
  ``"Invalid Request (HTTP 400, empty body)"``.
- `http_status` - HTTP status code, or None when the body was HTTP 200
  and the failure is an application errorCode.

<a id="viewtron.client.UnsupportedFeature"></a>

## UnsupportedFeature Objects

```python
class UnsupportedFeature(RuntimeError)
```

The connected firmware does not provide this command.

Raised when the LicensePlates commands are not available. The older
``GetVehiclePlate`` / ``AddVehiclePlate`` command family (``listType``,
``plateItemType``, ``pageIndex``, ``pageSize``) is not implemented:
its request and response shape is not confirmed, so this SDK does not
call those commands.

<a id="viewtron.client.CameraCapabilities"></a>

## CameraCapabilities Objects

```python
class CameraCapabilities()
```

What a camera reports about its API.

**Attributes**:

- `api_version` _str or None_ - ``apiVersion`` from GetDeviceInfo.
  When that field is missing, GetDeviceDetail is used.
- `http_post_version` _str or None_ - ``httpPostVersion`` from
  GetDeviceInfo, with the same GetDeviceDetail fallback.
- `config_version` _str or None_ - ``version`` attribute on the
  device's response ``<config>`` element. Outgoing requests
  still use config version 2.1.0.
- `supported_apis` _frozenset or None_ - Command names from
  GetSupportedAPIs. None when that command is not available
  (Invalid Request or HTTP 400).

<a id="viewtron.client.ViewtronCamera"></a>

## ViewtronCamera Objects

```python
class ViewtronCamera()
```

Client for Viewtron IP camera API with Basic HTTP authentication.

Sends commands to the camera over HTTP. Currently supports license plate
database management (CRUD), device info, and capability discovery.

Plate group ids are device-specific. On current firmware (observed on a
camera running 5.3.1, API 2.1.0) group 1 is ``temporaryList`` and the
allow list is ``whiteList``, typically group 2. Pass ``group=`` with
one of ``whiteList``, ``blackList``, or ``temporaryList``. The numeric
``group_id`` argument is still accepted. Omitting both uses ``"1"`` and
warns once per process. A future major release will default to
``whiteList``.

**Arguments**:

- `host` _str_ - Camera IP address (e.g., "192.168.0.20").
- `username` _str_ - Camera admin username.
- `password` _str_ - Camera admin password.
- `port` _int_ - HTTP port (default 80).
  

**Example**:

  from viewtron import ViewtronCamera
  
  camera = ViewtronCamera("192.168.0.20", "admin", "password")
  plates = camera.get_plates(group="whiteList")
  for plate in plates:
  print(plate["plate_number"], plate["owner"])

<a id="viewtron.client.ViewtronCamera.get_device_info"></a>

#### get\_device\_info

```python
def get_device_info()
```

Get camera device information.

**Returns**:

  dict with keys like 'deviceName', 'model', 'firmwareVersion',
  'apiVersion', and 'httpPostVersion' when the device sends them.

<a id="viewtron.client.ViewtronCamera.get_supported_apis"></a>

#### get\_supported\_apis

```python
def get_supported_apis()
```

Return the command names advertised by GetSupportedAPIs.

Names are read from ``applicationInterfaces/item`` and de-duplicated.
The ``count`` attribute is not trusted: devices have been observed
(a camera running 5.3.1 firmware, API 2.1.0) reporting a count that
does not match the number of items, with some names repeated.

**Returns**:

  frozenset of command names, or None when the device answers
  Invalid Request (errorCode 1) or HTTP 400. None means the
  command list is unknown (typical of 1.x firmware), not that
  the device has an empty API.
  
  The result is cached on this instance.

<a id="viewtron.client.ViewtronCamera.capabilities"></a>

#### capabilities

```python
@property
def capabilities()
```

Cached snapshot of api version, HTTP POST version, and commands.

``api_version`` and ``http_post_version`` come from GetDeviceInfo.
If either is missing, GetDeviceDetail (``detail/property``) fills
the gap. ``config_version`` is the response ``<config version>``.
``supported_apis`` is the set from ``get_supported_apis()``.

**Returns**:

  CameraCapabilities

<a id="viewtron.client.ViewtronCamera.get_plate_groups"></a>

#### get\_plate\_groups

```python
def get_plate_groups()
```

Return plate groups as ``{id: name}`` from GetLicensePlateGroups.

Ids are ints when they are numeric. On current firmware (observed
on a camera running 5.3.1, API 2.1.0) the groups are
``1`` temporaryList, ``2`` whiteList, and ``3`` blackList. Do not
hard-code those ids; call this method.

**Returns**:

  dict mapping group id to group name.
  

**Raises**:

- `UnsupportedFeature` - The device has no plate-group command.
- `ViewtronAPIError` - The camera returned another error.

<a id="viewtron.client.ViewtronCamera.add_plate"></a>

#### add\_plate

```python
def add_plate(plate_number, group_id="1", group=None)
```

Add a plate to the camera database.

**Arguments**:

- `plate_number` - The license plate (e.g., "ABC1234")
- `group_id` - Numeric group id. Defaults to ``"1"``. On current
  firmware (observed on a camera running 5.3.1, API 2.1.0)
  group 1 is the temporary list. The allow list is
  ``whiteList``, typically group 2. Relying on this default
  warns once.
- `group` - ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
  The id is resolved with ``get_plate_groups()``. When set,
  this overrides ``group_id``.
  

**Returns**:

  True if successful
  

**Raises**:

- `ViewtronAPIError` - The camera rejected the command. The top-level
  errorCode is checked before the per-item code.
- `UnsupportedFeature` - This firmware has no LicensePlates API.

<a id="viewtron.client.ViewtronCamera.add_plates"></a>

#### add\_plates

```python
def add_plates(plate_numbers, group_id="1", group=None)
```

Add multiple plates to the camera database.

**Arguments**:

- `plate_numbers` - List of plate strings
- `group_id` - Numeric group id. Defaults to ``"1"`` (the temporary
  list on current firmware; see ``add_plate``). Relying on
  this default warns once.
- `group` - ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
  Overrides ``group_id`` when set.
  

**Returns**:

  True if all successful
  

**Raises**:

- `ViewtronAPIError` - The camera rejected the command.
- `UnsupportedFeature` - This firmware has no LicensePlates API.

<a id="viewtron.client.ViewtronCamera.get_plates"></a>

#### get\_plates

```python
def get_plates(max_results=50, offset=1, group_id="1", group=None)
```

Query one page of the plate database.

**Arguments**:

- `max_results` - Maximum plates to return
- `offset` - Starting position (1-based — first plate is offset 1)
- `group_id` - Numeric group id. Defaults to ``"1"``. On current
  firmware (observed on a camera running 5.3.1, API 2.1.0)
  group 1 is the temporary list, so this default does not
  return allow-list plates. The allow list is ``whiteList``,
  typically group 2. Relying on this default warns once.
- `group` - ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
  Overrides ``group_id`` when set.
  

**Returns**:

  List of plate dicts with keys: plate_number, group_id,
  begin_time, end_time, owner, telephone. An empty database
  (errorCode 20, Resources Not Exist) returns ``[]``.
  

**Raises**:

- `ViewtronAPIError` - Any errorCode other than 0 or 20, including
  Invalid Request (1) and Range Error (16).
- `UnsupportedFeature` - This firmware has no LicensePlates API.

<a id="viewtron.client.ViewtronCamera.get_all_plates"></a>

#### get\_all\_plates

```python
def get_all_plates(group=None, group_id=None, page_size=50)
```

Return every plate, following ``resultOffset``, ``maxResult``, and ``total``.

**Arguments**:

- `group` - ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
  When omitted together with ``group_id``, every group from
  ``get_plate_groups()`` is read. That path does not use the
  ``"1"`` default and does not warn.
- `group_id` - Numeric group id for a single group. Ignored when
  ``group`` is set.
- `page_size` - Page size sent as ``maxResult``.
  

**Returns**:

  List of plate dicts, in group order then page order.
  

**Raises**:

- `ViewtronAPIError` - A page returned an error other than 0 or 20.
- `UnsupportedFeature` - This firmware has no LicensePlates API.

<a id="viewtron.client.ViewtronCamera.modify_plate"></a>

#### modify\_plate

```python
def modify_plate(plate_number,
                 group_id="1",
                 owner=None,
                 telephone=None,
                 group=None)
```

Update an existing plate's details.

**Arguments**:

- `plate_number` - Plate to modify (must already exist)
- `group_id` - Numeric group id. Defaults to ``"1"`` (the temporary
  list on current firmware; see ``add_plate``). Relying on
  this default warns once.
- `owner` - New owner name (optional)
- `telephone` - New phone number (optional)
- `group` - ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
  Overrides ``group_id`` when set.
  

**Returns**:

  True if successful
  

**Raises**:

- `ViewtronAPIError` - The camera rejected the command.
- `UnsupportedFeature` - This firmware has no LicensePlates API.

<a id="viewtron.client.ViewtronCamera.delete_plate"></a>

#### delete\_plate

```python
def delete_plate(plate_number, group_id="1", group=None)
```

Delete a plate from the database.

**Arguments**:

- `plate_number` - Plate to delete
- `group_id` - Numeric group id. Defaults to ``"1"`` (the temporary
  list on current firmware; see ``add_plate``). Relying on
  this default warns once.
- `group` - ``"whiteList"``, ``"blackList"``, or ``"temporaryList"``.
  Overrides ``group_id`` when set.
  

**Returns**:

  True if successful
  

**Raises**:

- `ViewtronAPIError` - The camera rejected the command.
- `UnsupportedFeature` - This firmware has no LicensePlates API.

