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

## Battery reporting and power-off menu

The receiver reported battery byte `00` once during reconnect, then `02` (40%)
1.164 seconds later. Steam warns below 20%, so this transient is a plausible
source of the reported warning. We did not capture the warning itself and
cannot explain the earlier full indication from this sample.

Identity replies are retained even before the joystick opens. However, publishing
that value during open or immediately on the next device update left Steam at
100% despite the driver reporting 40%: the early event was missed. Keep the
ordinary asynchronous receiver-reply notification instead. Unknown states use
-1 rather than 0. The early-publication attempt was removed after the Steam check.
Before publishing an empty battery, request confirmation after two seconds.
A sustained zero still gets reported. The extra query is attempted once even
if it fails; ordinary heartbeat requests remain available. Other battery
levels and charging changes publish immediately.

`python3 validation/replay-flydigi-battery.py` exercises initial caching,
the captured zero-to-40% sequence, sustained zero, failed queries, unknown
state and charging transitions. The native 32-bit build and physical probe
passed. This is not a discharge/capacity calibration; firmware levels are
coarse 20% steps.

Steam's Turn Off Controller call emitted no USB output in a five-second capture
while input continued. There is no power-off operation in this SDL driver.
The examined Flydigi SDK has only legacy XInput/DInput sleep implementations,
not a dedicated NewXInput implementation. Do not send NewXInput command 0x16
as a guessed sleep command: it changes joystick sensitivity in that protocol.
The Steam menu is therefore not implemented for this device in this setup.

## Rumble framing

Steam Identify reached the receiver, but USB showed `03 5A A5 12 06 7F 7F
00 00 00` and its stop packet. The Vader receiver uses unnumbered reports:
HIDAPI needs a zero report-ID byte, which it strips before sending. The existing
WritePacket helper handled this for configuration, but rumble uses the separate
asynchronous SDL rumble worker and bypassed that helper. Set the Vader V2
rumble packet's report-ID byte to zero before queueing it. Keep the worker and
other models' report framing unchanged.

The actual callback replay checks start/stop levels, V1 and other V2 behavior,
and write errors. Physical vibration and the corrected Steam USB capture are
separate validation steps.

## Four-motor candidate (October 9)

The official SDK's NewXInput vibration command carries separate left/right grip
and left/right trigger levels. The previous SDL trigger callback returned
unsupported. The candidate implements it for confirmed device ID 130 and
advertises trigger-rumble capability only for that device. Other identities are
unchanged. Each command carries all four levels, so the callbacks retain the
other pair's current levels; stopping either pair must not stop the other.
Cached levels change only when the rumble worker accepts the packet and are
cleared when opening the joystick.

The callback replay verifies simultaneous levels, independent stop commands,
failed writes, model capability gating, and unchanged V1/other V2 framing.
Existing button (12,289 cases), discovery/reconnect and battery replays pass.
The complete native 32-bit SDL library also builds in the existing image builder.
Build SHA-256: 773f9edb36ed2595d893375b738676501264424102d052f348da24a1c105e460.
There is an existing unused GetReply warning. This candidate has not been loaded
into Steam or physically tested; the installed driver is unchanged.

Next checks: isolated left grip, right grip, left trigger, right trigger; mixed
levels; stop one pair while the other continues; reconnect with all motors off;
then verify the streaming path reaches the same callbacks. Firmware vibration
settings may gate trigger response. Do not infer physical output from a queued
USB packet or advertise end-to-end support before those checks.

Changes are kept in Cynary's fork. SDL upstream does not accept AI-generated
contributions; no upstream PR is being submitted.

## Vader 5 motion input

On 2026-10-09 the installed driver exposed gyro capability to Steam. Steam's
own input-state feed reported gyro speed, acceleration and an integrated
orientation quaternion. Sensor delta time was 2000 microseconds; the passive
native capture received 21,343 reports over 45 seconds (474 reports/s), and
Steam's sampled estimate was 486 reports/s. These are delivery counts, not a
measurement of the USB polling interval. The controller was mostly stationary;
physical axis directions and gyro-to-mouse gameplay remain to be checked.

Sensor capability registration used the Vader 4 wireless rate (1000 Hz) even
for Vader 5, whose timestamp step is 2 ms. It now derives the advertised rate
from the already selected model/connection timestamp step. This changes metadata,
not timestamp progression or raw data conversion. The actual V2 parser replay
now checks gyro/acceleration axes, physical units, timestamp increments and
sensor-disable behavior. Button, reconnect, battery and rumble replays pass.
The 32-bit library compiled successfully; it has not replaced the running one.
