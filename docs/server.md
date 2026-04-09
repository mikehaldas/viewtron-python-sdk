# Table of Contents

* [viewtron.server](#viewtron.server)
  * [ViewtronServer](#viewtron.server.ViewtronServer)
    * [serve\_forever](#viewtron.server.ViewtronServer.serve_forever)
    * [shutdown](#viewtron.server.ViewtronServer.shutdown)

<a id="viewtron.server"></a>

# viewtron.server

Viewtron HTTP Server — receives alarm events from Viewtron IP cameras and NVRs.

Handles all the connection details that Viewtron cameras require:
HTTP/1.1 persistent connections, keepalive responses, XML success replies,
and multi-threaded request handling.

Usage:
    from viewtron import ViewtronServer

    def on_event(event, client_ip):
        print(f"[{event.category}] {event.get_alarm_type()} from {client_ip}")
        if event.category == "lpr":
            print(f"  Plate: {event.get_plate_number()}")
            print(f"  Authorized: {event.is_plate_authorized()}")

    server = ViewtronServer(port=5050, on_event=on_event)
    server.serve_forever()

You can find Viewtron IP cameras at https://www.Viewtron.com

Written by Mike Haldas
mike@cctvcamerapros.net

<a id="viewtron.server.ViewtronServer"></a>

## ViewtronServer Objects

```python
class ViewtronServer()
```

HTTP server that receives events from Viewtron IP cameras.

**Arguments**:

- `port` - Port to listen on (default 5050)
- `on_event` - Callback function(event, client_ip) called for each
  parsed alarm event. event is a ViewtronEvent instance with
  .category, .get_alarm_type(), .get_plate_number(), etc.
- `on_connect` - Optional callback(client_ip) called when a camera
  first connects (sends its first keepalive).
- `on_raw` - Optional callback(xml_text, client_ip) called with the
  raw XML body of every POST (before parsing). Useful for
  logging or debugging.
  

**Example**:

  from viewtron import ViewtronServer
  
  def on_event(event, client_ip):
  if event.category == "lpr":
  plate = event.get_plate_number()
  authorized = event.is_plate_authorized()
  print(f"Plate {plate} - Authorized: {authorized}")
  
  server = ViewtronServer(port=5050, on_event=on_event)
  server.serve_forever()

<a id="viewtron.server.ViewtronServer.serve_forever"></a>

#### serve\_forever

```python
def serve_forever()
```

Start the server and block until interrupted.

<a id="viewtron.server.ViewtronServer.shutdown"></a>

#### shutdown

```python
def shutdown()
```

Stop the server from another thread.

