# Native and Xbox fallback on Linux

Flydigi receivers expose a native HID interface and an Xbox-compatible interface.
When native mode takes control, Xbox reports stop. SDL previously kept that
interface visible, including its last held-button state. Steam could then list
the same controller twice and retain an A press after switching modes.

The Linux backend now removes the fallback when the native controller connects.
Its normal removal path releases held buttons and recenters axes. When the
native controller disconnects or permission is disabled, Linux rescans for the
fallback; this transition does not generate a udev event by itself. Other
platform backends are unchanged.

Validation on a Vader 5 Pro, firmware 7.1.5.0:

- Before the change, Steam listed native and Xbox entries simultaneously. The
  Xbox entry retained an A press while the native entry was neutral.
- After restarting with the candidate, Steam listed one native controller.
- Disabling native permission switched to one Xbox entry; re-enabling it switched
  back to one native entry with all ten extra-button mappings. Neither transition
  required restarting Steam.
- `python3 validation/replay-linux-handoff.py` tests the actual reconciliation
  function with a modeled device list, including head/middle/tail removals,
  repeated transitions and a state change during enumeration.
- `python3 validation/replay-flydigi.py` passes 12,289 parser cases.

Physical reconnect, LM/RM Steam events and assigned-action delivery remain to
be tested. Multiple identical receivers have not been tested. The existing HID
backend matches devices by vendor/product; this change retains that limitation.

Written with Codex and kept in this fork; no upstream contribution is proposed.

## Controller off when Steam starts

A later physical test found a separate startup failure: Steam had no open fd for
its Flydigi HID interface, while the receiver retained native permission. Only
the generic Xbox pad appeared. The synchronous initialization had failed while
the controller was off and the driver was detached; turning the wireless
controller on does not re-enumerate its USB receiver.

V2 initialization now waits for replies in the normal nonblocking report loop.
Until it has a valid identity and an open native joystick, it makes bounded-rate
information/status queries (at most one discovery round per second). Firmware
version validation precedes native availability, and recovery does not alter
the user's native permission setting. An open joystick retains its existing
heartbeat. `replay-flydigi-reconnect.py` checks delayed initialization, validation,
query timing and suppression of discovery traffic while the joystick is open.

The live candidate loaded successfully and restored one native Steam controller
and roughly 500 raw reports per second. Physical off/on and startup with the
controller off still require validation before rebuilding/promoting the image.

## Silence caused an unbounded acquisition loop

The next physical off/on test failed. A five-second USB capture contained 1,102
acquisition requests and 1,103 identity requests, with no input reports. The
100 ms receive timeout reset the heartbeat deadline on every event-loop pass,
so unanswered requests were retried continuously instead of every 30 seconds.
This behavior existed in the original heartbeat code; asynchronous discovery
alone did not fix it. The capture proves the flood, but does not establish
whether it caused the initial wireless failure.

An open controller now retries after silence at most once per second, measured
from the last attempt even when the write fails. Normal input retains the
30-second heartbeat. Recovery also requests mapping status. Availability is
reconciled against the actual joystick list, and each received packet refreshes
its joystick pointer in case the preceding packet disconnected the device.

The C replay test covers ten seconds of silence at a 500 Hz event-loop rate,
resumed input, the normal heartbeat and failed writes. The new live build showed
only ten discovery rounds during a ten-second capture. At that point identity
replies were present, but mapping-status replies and raw input remained absent;
physical recovery was not yet confirmed. Do not interpret the bounded traffic
check as a successful reconnect test.
