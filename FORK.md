# Moonmachine SDL experiment

This branch is an altered SDL build for Moonmachine. It starts at
`70e9cc86ddbe0f6b580c3c02d1391b3dde4d11fb`, the public commit reported by the
Steam client used for testing.

The Vader 5 Pro's raw input reports include a Turbo button at byte 14, bit 1.
The native driver already reads the other extended buttons but omits this one.
This branch adds joystick button 20 and maps it to SDL's otherwise-unused
`misc1` slot for this model. Fn remains button 19 / `misc6`. No existing button
is renumbered and other models keep their previous button counts.

The change does not implement rapid-fire or macros. Those are separate firmware
features. Exposing the raw button lets applications choose their own binding.

## Validation so far

- Built a joystick-only shared library on the K17 in a disposable build directory.
- `python3 validation/replay-flydigi.py` passes 12,289 synthetic mixed/repeated/release
  reports through the actual V2 parser extracted from this source tree.
- The same replay against the unmodified base fails on Turbo, establishing that
  the test detects the missing event.
- The compiled library's `SDL_GetGamepadMappingForGUID` returns `misc1:b20` and
  preserves all previous mappings for the Vader 5 Pro HIDAPI GUID.

This is not yet installed in Steam. Physical input, Steam's binding UI and both
Steam library architectures still need validation. The joystick-only build is
not suitable for replacing Steam's complete SDL library.

This fork's patch and validation harness were written with Codex. SDL's upstream
policy prohibits AI-generated code contributions; no upstream PR is being sent.
Upstream authorship and licensing notices are retained.
