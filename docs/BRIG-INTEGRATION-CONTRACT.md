# BRIG RPG 2 — Integration Contract

## First-person view controls

The first-person presentation controls belong to the **client DLL**. They are local user preferences and must not be synchronized through server settings, map configuration, Co-op/DeathMatch rules, or shared gameplay state.

### Ownership and behavior

| Setting | Owner / effect |
| --- | --- |
| `default_fov` | Client HUD FOV default; the server's `SetFOV` message can temporarily override it for zoom, and `SetFOV 0` restores the current default. |
| `viewmodel_fov` | Client first-person entity only. GoldSrc's shared scene projection is not replaced; the value is approximated by scaling the viewmodel's geometry in the client Studio renderer. |
| `viewmodel_offset_x` | Moves the first-person entity along its camera-relative right axis. |
| `viewmodel_offset_y` | Moves the first-person entity along its camera-relative forward axis. |
| `viewmodel_offset_z` | Moves the first-person entity along its camera-relative up axis. |
| `cl_righthand` | Archived local preference: `1` is right-hand/default; `0` mirrors the first-person model hierarchy for left-hand presentation. |

The "viewmodel" here means any Studio model rendered as the local first-person presentation entity, not just weapon models: it can include arms, held items, tools, props, and other first-person models. The settings are selected by the engine's `GetViewModel()` entity identity, not by a weapon class or model filename.

The offset code modifies the engine's viewmodel entity origin, not `ref_params_s::vieworg`, the player's predicted origin, collision, or server coordinates. The renderer applies the FOV-like scale and handedness only when the current Studio entity is `gEngfuncs.GetViewModel()`. Player entities and ordinary world studio entities must remain unaffected.

Hand reflection is performed on root-bone transforms so child bones inherit it with their animation. It does not replace model assets, edit model files, or change the local player's character model. Both hardware and software Studio transform paths should be checked in-game; the exact visual result remains dependent on the viewmodel asset's rig and authored orientation.

### Commands

- `viewmodel_presetpos 1|2|3`: applies four archived viewmodel CVAR values.
- `switchhands`: toggles `cl_righthand`.
- `switchhandsleft`: sets `cl_righthand 0`.
- `switchhandsright`: sets `cl_righthand 1`.

A preset is only a starting layout. Users can subsequently edit each CVAR independently; the individual CVARs, rather than a hidden preset state, are authoritative and archived.

### Required validation

| Area | Validation |
| --- | --- |
| Registration | Confirm all CVARs and commands appear in the in-game console after client HUD initialization. |
| Persistence | Change each archived CVAR, restart the game, and confirm the value remains. |
| Presets | Test arguments `1`, `2`, `3`, missing arguments, extra arguments, and malformed text. Confirm all four values change for valid presets only. |
| Offsets | Confirm X/Y/Z move only the first-person entity and never move the camera, collision, or remote player models. Test limits and all standard first-person model types. |
| Viewmodel FOV | Test values 54 and 68 and intermediate values. Confirm world FOV and scoped/zoom FOV remain unchanged. Inspect animations and clipping. |
| Handedness | Test both hand states with every available first-person model, animated sequences, weapon/item changes, spectator in-eye view, and both renderer modes where supported. Confirm remote player models are unchanged. |
| Default FOV | Test normal play, zoom in/out, changing `default_fov` during play, map changes, demo playback/recording, spectator, and intermission. Confirm sensitivity restores when the default FOV is active. |
| Build | Build `Release | Win32` with the repository's Visual Studio solution and run the repository tests. |

The Windows x86 CI workflow is the automated build authority. A successful DLL build does not replace a Steam Legacy runtime check; runtime-only cases must be reported separately when that environment is unavailable.
