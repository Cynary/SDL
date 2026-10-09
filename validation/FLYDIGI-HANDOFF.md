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
