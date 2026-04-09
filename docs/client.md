# Table of Contents

* [viewtron.client](#viewtron.client)
  * [ViewtronCamera](#viewtron.client.ViewtronCamera)
    * [get\_device\_info](#viewtron.client.ViewtronCamera.get_device_info)
    * [add\_plate](#viewtron.client.ViewtronCamera.add_plate)
    * [add\_plates](#viewtron.client.ViewtronCamera.add_plates)
    * [get\_plates](#viewtron.client.ViewtronCamera.get_plates)
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
  camera.add_plate("ABC1234")
  plates = camera.get_plates()
  camera.modify_plate("ABC1234", owner="Mike", telephone="555-1234")
  camera.delete_plate("ABC1234")
  
  # Device info
  info = camera.get_device_info()
  
  Written by Mike Haldas
  mike@cctvcamerapros.net
  https://www.Viewtron.com

<a id="viewtron.client.ViewtronCamera"></a>

## ViewtronCamera Objects

```python
class ViewtronCamera()
```

Client for Viewtron IP camera API with Basic HTTP authentication.

Sends commands to the camera over HTTP. Currently supports license plate
database management (CRUD) and device info queries.

**Arguments**:

- `host` _str_ - Camera IP address (e.g., "192.168.0.20").
- `username` _str_ - Camera admin username.
- `password` _str_ - Camera admin password.
- `port` _int_ - HTTP port (default 80).
  

**Example**:

  from viewtron import ViewtronCamera
  
  camera = ViewtronCamera("192.168.0.20", "admin", "password")
  plates = camera.get_plates()
  for plate in plates:
  print(plate["plate_number"], plate["owner"])

<a id="viewtron.client.ViewtronCamera.get_device_info"></a>

#### get\_device\_info

```python
def get_device_info()
```

Get camera device information.

**Returns**:

  dict with keys like 'deviceName', 'model', 'firmwareVersion', etc.

<a id="viewtron.client.ViewtronCamera.add_plate"></a>

#### add\_plate

```python
def add_plate(plate_number, group_id="1")
```

Add a plate to the camera database.

**Arguments**:

- `plate_number` - The license plate (e.g., "ABC1234")
- `group_id` - Group ID ("1" = default/allow list)
  

**Returns**:

  True if successful

<a id="viewtron.client.ViewtronCamera.add_plates"></a>

#### add\_plates

```python
def add_plates(plate_numbers, group_id="1")
```

Add multiple plates to the camera database.

**Arguments**:

- `plate_numbers` - List of plate strings
- `group_id` - Group ID ("1" = default/allow list)
  

**Returns**:

  True if all successful

<a id="viewtron.client.ViewtronCamera.get_plates"></a>

#### get\_plates

```python
def get_plates(max_results=50, offset=1, group_id="1")
```

Query the plate database.

**Arguments**:

- `max_results` - Maximum plates to return
- `offset` - Starting position (1-based — first plate is offset 1)
- `group_id` - Group ID to query
  

**Returns**:

  List of plate dicts with keys: plate_number, group_id,
  begin_time, end_time, owner, telephone

<a id="viewtron.client.ViewtronCamera.modify_plate"></a>

#### modify\_plate

```python
def modify_plate(plate_number, group_id="1", owner=None, telephone=None)
```

Update an existing plate's details.

**Arguments**:

- `plate_number` - Plate to modify (must already exist)
- `group_id` - Group the plate belongs to
- `owner` - New owner name (optional)
- `telephone` - New phone number (optional)
  

**Returns**:

  True if successful

<a id="viewtron.client.ViewtronCamera.delete_plate"></a>

#### delete\_plate

```python
def delete_plate(plate_number, group_id="1")
```

Delete a plate from the database.

**Arguments**:

- `plate_number` - Plate to delete
- `group_id` - Group the plate belongs to
  

**Returns**:

  True if successful

