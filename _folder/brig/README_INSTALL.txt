BRIG RPG 2 - Windows / Steam Half-Life (steam_legacy)

1. Install Half-Life in Steam. Properties -> Betas -> steam_legacy.
2. Extract the brig folder beside hl.exe:
   Steam/steamapps/common/Half-Life/brig/liblist.gam
   Do not put brig inside valve or svencoop.
3. Restart Steam, then start Brig RPG 2 from the library, or use:
   hl.exe -game brig -console
4. New Game starts c0a0; Hazard Course starts t0a0.
   Console smoke tests: map c0a0, map t0a0, map crossfire.

Release ZIPs include brig/cl_dlls/client.dll and brig/dlls/hl.dll,
built from this repository for Windows x86. A source checkout needs these
DLLs built first; see BUILDING.md. No Sven Co-op or Counter-Strike install
is required to load the mod. The Steam Half-Life engine is still required.

The base HL models, HUD, sound bank and maps are retained. Extra resource
collections do not add weapons, NPC code, Sven mechanics or CS game rules.
models/svencoop and sound/svencoop contain the integrated Sven collection;
addon resources win matching Sven paths, without replacing the HL base.
models/cstrike and models/cstrike_hd contain only non-player models.
The supplied cstrike/sound has text metadata, but no audio samples.
Event model variants have separate svencoop_event_* directories.

_Extra directories contain selectable alternatives and preserved originals.
brig/_Extra is an INACTIVE archive: its Sven maps/configs/replacement lists
are not compatible HL1 entry points and must not be copied into active paths.
Extras are sorted into models/_Extra, sound/_Extra, sprites/_Extra,
gfx/_Extra, resource/_Extra and docs/_Extra. Stable variant IDs keep paths
short; docs/brig-assets.json in the repository maps every resource to its
original name. Conflicting HUD sprite binaries are never overwritten.

The client ignores HLTV stufftext on the legacy API, which lacks the newer
filtered command callback. Engine and gameplay still require an in-game
smoke test on a real steam_legacy installation; CI checks cannot replace it.
