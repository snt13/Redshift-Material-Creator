# Changelog — Redshift Material Creator

Cinema 4D Python tool that batch-builds Redshift node materials from a folder
of PBR texture maps. Newest first.

Moved out of the script's docstring at v2.3 — it had grown to about 550 lines,
roughly a third of the file, which made the source tedious to scroll.

---

## v2.7 — 2026-09-11

### Changed

- The texture extension whitelist is narrowed to the seven formats actually
  used:

      .png  .jpg  .jpeg  .tif  .tiff  .exr  .tga

  Dropped: `.tx`, `.hdr`, `.bmp`, `.psd`, `.iff`, `.dds`, `.webp`. A `.psd`
  sitting next to an export is a working file, not a map to load, and
  Redshift would not have read half of the others as a texture anyway.

  Matching stays case-insensitive, so `.PNG` and `.EXR` are still found.

### Added

- Four more tests (53 total): the whitelist is exactly those seven, every one
  of them is picked up, the dropped formats are ignored, and uppercase
  extensions still match.

---

## v2.6 — 2026-09-11

### Changed

- The AO row is out of Texture Channels again. One control now: the **AO**
  checkbox in Options. Its keywords are the module constant `AO_KEYWORDS`
  (`AmbientOcclusion, Ambient_Occlusion, Occlusion, AO`), and they are only
  searched for when that box is ticked.

      AO on  + a map in the set  ->  BaseColor x AO map
      AO on  + no map            ->  procedural AO node
      AO off                     ->  no AO, and no AO search at all

  AO stays a real channel internally, so the map is still loaded RAW, still
  gets its own TriPlanar, and is still handled by the Game Asset splitter.

### Fixed

- **The short `AO` keyword matched letters inside other words.** Matching
  normally ignores separators entirely — that is what lets `base color` match
  `BaseColor` — but it also means a two-letter keyword matches anywhere, and
  `Cacao_BaseColor.png` was being collected as an AO map. Confirmed live, not
  theorised: the first v2.6 build did exactly that.

  `extract_identifier()` takes a `require_boundary` flag, and the channels in
  `BOUNDARY_MATCH_CHANNELS` (just AO) use it: the keyword must sit against a
  separator or the start/end of the name. If the last occurrence fails that
  test the search walks backwards to an earlier one, so `AO_Cacao.png` still
  resolves correctly.

  This matters more now than it would have in v2.5, because with no keyword
  field there is no way for you to work around it.

### Added

- `Ambient_Occlusion` to the recognised spellings.
- Seven more tests (49 total): boundary matching accepts a delimited keyword,
  accepts one spanning a separator, rejects letters inside a word, falls back
  to an earlier occurrence, and — through a real folder scan — `Cacao` is not
  an AO map. Plus: AO has no row in the dialog's channel lists.

---

## v2.5 — 2026-09-11

### Added

- **A baked AO map is used instead of the procedural AO node when the texture
  set has one.** The AO checkbox keeps its meaning — "apply ambient occlusion"
  — but how it gets there now depends on what is on disk:

  | AO checkbox | AO map in the set | Result |
  |---|---|---|
  | off | — | no AO, unchanged |
  | on | yes | BaseColor × AO map → Base Color |
  | on | no | procedural Redshift AO node, unchanged |

  The map is multiplied into the base colour through an `rsmathmulvector`
  node named "AO Multiply", after the BaseColor Color Correct. That is the
  standard way to apply a baked AO and it is what the old procedural node was
  only approximating.

- **AO is now a proper texture channel**, with its own row in Texture
  Channels and an editable keyword list (`AmbientOcclusion, Occlusion, AO`) —
  AO map naming varies more between exporters than any other channel, so
  hardcoding it would have been wrong. Being a real channel means it also
  gets loaded RAW, goes through its own TriPlanar when Triplanar is on, and
  is split by the Game Asset ColorSplitter like the other greyscale maps.

  This was the "real AO map" item on the v1.1 known-limitations list, where
  it had been sitting since the beginning.

  A note on the short `AO` keyword: matching ignores separators, so a
  filename containing the letters "ao" together (`Cacao_BaseColor.png`) can
  be picked up as an AO map. If that ever bites, drop `AO` from the keyword
  field and keep the longer spellings.

### Changed

- The AO texture sampler is only built when the AO checkbox is on. Loading an
  AO map into a material that is not using it would leave an orphan node in
  the graph.

### Verified in Cinema 4D

- AO off with a map present → map ignored, no AO nodes (6 nodes)
- AO on with a map → `BaseColor CC → AO Multiply ← AO Tex → Base Color` (8)
- AO on with no map → procedural `AO` node, as before (7)
- AO on with a map and Triplanar → the AO map gets its own TriPlanar driven
  by the shared Size node (12)

---

## v2.4 — 2026-09-11

### Added

- Models are paired with materials BY FOLDER, with name matching kept as the
  fallback. Each material set now remembers the folder its textures were found
  in (`scan_folder` returns a third value, `set_folders`, and each set carries
  a `sourceFolder`). A model imported from that folder — or from its parent or
  a subfolder of it — gets that set's material, whatever the mesh inside the
  FBX happens to be called.

  This is what makes the common "one folder per asset" layout work. Before
  this, pairing was purely substring matching on the object name, so a folder
  full of correctly organised assets still ended up untextured if the meshes
  were called `polySurface1` or `Mesh_001` — which plenty of exporters do by
  default.

  Order of resolution:
  1. one material in the run → it goes on everything (unchanged)
  2. exactly one texture set shares the model's folder → that one
  3. several sets share the folder → the object's name picks between them,
     then across all sets
  4. no folder relation → name matching across all sets, as before
  5. nothing matches → object left alone and reported, as before

- `folder_candidates()` and `name_candidate()` — the two matching rules pulled
  out as pure functions, so both are unit tested. Closeness is scored: same
  folder beats one-level-apart beats two, and the closest set wins when
  several are related.

- Preview Materials shows each set's folder when Import 3D Model is ticked, so
  you can see the pairing before committing to it.

- 13 more tests (39 total) covering folder scoring — model beside its
  textures, textures in a `textures/` subfolder, model in a `mesh/` subfolder,
  closest-wins, several sets in one folder, unrelated folders, trailing
  separators — and the name-matching rules.

### Fixed

- The texture tag was inserted FIRST on each object. `InsertTag()` with no
  predecessor puts the tag at the front of the list, and Cinema 4D gives
  precedence to the RIGHTMOST texture tag — so an FBX that carries its own
  materials (most of them do) would have silently overridden the material this
  tool just assigned. The tag now goes last. Present since v1.1; found by
  testing the import against real geometry rather than in isolation.

### Changed

- Models are imported one file at a time instead of all at once. A single
  merge at the end made it impossible to tell which object came from which
  file, and that origin is what the folder pairing needs.
- The console reports how the tagging was decided: how many objects matched by
  folder, by name, and by the single-material shortcut.

---

## v2.3 — 2026-09-10

### Changed

- The changelog moved out of the module docstring and into this file. The
  script header is now nine lines: what the tool does, how to run it either
  way, and pointers to this file and to the tests. No behaviour change —
  the script went from 2098 to 1556 lines.

---

## v2.2 — 2026-09-10

### Fixed

- "Displacement" was clipped to "Displaceme" in the Texture Channels
  list - the same too-narrow-checkbox problem as "Game Asset" in
  v2.1, at 110 again. The channel column is now CHANNEL_LABEL_WIDTH
  (150), sized off the longest label with room to spare.

  Every fixed width in the dialog has been checked: the two checkbox
  columns are the only ones, and both are now named constants at the
  top of the file. Every other label uses initw=0, which sizes itself
  to its text and cannot clip.

---

## v2.1 — 2026-09-10

### Removed

- Settings persistence and the rs_material_creator.json file it wrote
  beside Cinema 4D's preferences. The dialog opens on its defaults
  every time again. (If you ever want it back it was
  settings_path / load_settings / save_settings plus the dialog's
  persistable / apply_persisted - see v1.9.)

### Fixed

- "Game Asset" was clipped. A checkbox whose initw is narrower than
  its label gets cut off rather than wrapped, and 110 was not enough.
  The three Options columns now have named widths (OPT_COL_1/2/3) with
  column 1 deliberately wider than it needs to be, which also moves
  AO and Copy Textures further right and clear of it.

---

## v2.0 — 2026-09-10 (UI pass)

### Changed

- The dialog is grouped into three bordered sections - Source,
  Texture Channels, Options - instead of one long stack of rows.
  The Options block is a 3x3 grid so the checkboxes line up in
  columns rather than wrapping wherever they land:

      [ ] Triplanar    Size: [0.01]
      [ ] Curvature    [ ] AO           [ ] Flip Green (DirectX)
      [ ] Game Asset   [ ] Copy Textures  [ ] Import 3D Model

  Triplanar and Curvature now sit with the other options rather than
  hanging off the bottom on their own.
- Material Name starts BLANK, with "blank = texture name" beside it.
  Leaving it empty names each material after its texture set, which
  is the common case. GeDialog has no placeholder text, so this is a
  label next to the field, not a value sitting in it - nothing can
  leak into a material name.
- Flip Green (DirectX) now defaults to OFF, in the dialog and in the
  code. Substance does export DirectX normals, but plenty of sources
  are already OpenGL, and a wrong flip is harder to spot than a
  missing one - so it is opt-in. (v1.1 had defaulted it on.)

### Fixed

- Preview Materials: clicking OK did nothing and the window just sat
  there. AddDlgGroup draws the button but the click still has to be
  handled - PreviewDialog had no Command(), so it was swallowed.
- AO is no longer greyed out when Curvature is ticked. v1.9 made them
  mutually exclusive, which was a judgement call the tool had no
  business making - they touch different parts of the graph and
  running both is a legitimate look. The only thing that greys out
  now is the Size field when Triplanar is off.

---

## v1.9 — 2026-09-10 (the durability pass - tier 1 + tier 3 of the review)

### Added

- UNDO. The whole batch - materials, imported objects, texture tags -
  is one undo step. Ctrl+Z after creating thirty materials now
  removes thirty materials. Previously nothing was undoable at all.
- Runs as a PLUGIN as well as a Script Manager script, from the same
  file. Keep the .py extension and hit Execute in the Script Manager
  as always; or copy it into a Cinema 4D "plugins" folder and rename
  it to .pyp, and it registers a command you can put in a menu or bind
  to a shortcut. The file extension is what decides
  (_running_as_plugin), so neither way is second class.
  NOTE: PLUGIN_ID is a placeholder. Register a real one at
  developers.maxon.net before sharing this with anyone - unregistered
  ids can collide with another plugin.
- SETTINGS PERSIST. Keywords, checkboxes, size, folder, material name
  and the existing-material policy are written to
  rs_material_creator.json beside Cinema 4D's preferences, saved when
  you hit Create and when you close the dialog, and reloaded on open.
  No more retyping keyword lists every session.
- "If material exists" dropdown - Update texture paths (default),
  Create new, or Skip. Update repoints the paths on the material
  already in the scene and leaves the rest of the graph alone, so
  ramp tweaks, colour corrections and curvature settings survive a
  re-run. It finds the nodes by the names the builder gives them
  ("BaseColor Tex" and friends), so it only works on generated
  materials; anything it cannot find is reported.
- Progress. The build reports through Cinema 4D's status bar (which
  repaints during a long loop, unlike a dialog gadget) and a status
  line at the bottom of the dialog. Fifty materials no longer look
  like a freeze.
- Unit tests - test_material_creator.py, run with plain
  `python test_material_creator.py` OUTSIDE Cinema 4D. It stubs c4d
  and maxon, then exercises the filename parsing and folder scanning:
  26 tests over extract_identifier, strip_normal_format_tokens,
  identifier_key, build_material_name, safe_folder_name and
  scan_folder.

### Changed

- Materials are created DIRECTLY - c4d.BaseMaterial(c4d.Mmaterial),
  GetNodeMaterialReference(), CreateDefaultGraph(), InsertMaterial().
  The old c4d.CallCommand(1040254, 1012) fired the Redshift preset
  menu and then grabbed whatever GetActiveMaterial() returned: it
  depended on an undocumented menu id, hijacked the active material,
  and gave no handle on insertion, which is what undo needs. The
  material is now inserted only once its graph is finished, so it
  never appears half-built.
- The dialog is ASYNC and stays open. Create Material does the work
  in place instead of closing first, so you can adjust settings and
  run again without reopening. The Create button disables itself
  while a build is running.
- Preview Materials opens a scrollable read-only window instead of
  gui.MessageDialog, which was unreadable and could truncate with
  many texture sets.
- Copy Textures writes to tex/<material name>/ instead of a single
  flat tex/ folder, and skips a copy onto itself.
- AO and Curvature are mutually exclusive in the UI - both push a
  procedural occlusion signal into the same material and fight each
  other. Ticking Curvature greys out AO.
- The Size field greys out when Triplanar is off.

### Fixed

- strip_normal_format_tokens() left a doubled separator when the
  token was in the MIDDLE of the name: "Wood_OpenGL_2K" came out as
  "Wood__2K", so a material could be named with a double underscore
  depending on which file the scan happened to see first. Present
  since v1.1; found by the new tests within a minute of writing them,
  which is the argument for having them.
- Copy Textures used to copy every map into one flat tex/ folder with
  shutil.copy2, so two texture sets that each export a BaseColor.png
  silently overwrote each other and the second material ended up
  pointing at the first one's map.
- Re-running on the same folder no longer produces Material,
  Material.1, Material.2 - see the "If material exists" dropdown.

### Still open (Tier 2, Deliberately Deferred)

- Packed ARM/ORM/RMA maps, a real AO map, extra channels (Emission,
  Translucency, Transmission, SSS), UDIM, a colorspace dropdown for
  ACES, displacement scale controls.
- Preview does not yet let you deselect individual texture sets
  before creating - it is scrollable now, but still read-only.
- Named presets (Substance / Megascans / Poliigon) on top of the
  settings file.

---

## v1.8 — 2026-09-10

### Removed

- The Size reroutes. Size now wires straight into each TriPlanar's
  Scale. Six short wires from one node read more cleanly than six
  wires plus six dots, and the reroute column was adding clutter
  without earning it.
- GraphBuilder.add_reroute() / reroute_in() / reroute_out() /
  connect_ports() and REROUTE_NODE_ID, all unused once the reroutes
  were gone.

### Fixed (In The Same V1.8, Caught Before It Mattered)

- The first cut of this removal deleted the wrong slice of
  GraphBuilder: it duplicated set_value() and set_color() and left
  the reroute helpers behind, one of which still referenced the
  deleted REROUTE_NODE_ID and would have raised NameError if
  anything had called it. Nothing did, and the later duplicate
  definitions were identical, so the behaviour was correct - but the
  class is now clean: __init__, warn, add, set_name, port, connect,
  connect_from, set_value, set_color, disconnect, set_texture,
  find_single.
- The "Created N materials." dialog after Create Material. The
  materials appearing in the Material Manager is confirmation enough,
  and the count still goes to the console.

  A dialog DOES still appear when a material failed to build or a
  node or port could not be wired - handing back a quietly broken
  material is worse than a popup. A clean run is silent.

---

## v1.7 — 2026-09-10

    SETTLED: node positions cannot be set from Python. Stop trying.

  Two tests, both negative:
    1. Wrote deliberately extreme positions into
       "net.maxon.ui.position" - three nodes stacked 1500 units apart
       in one column, two more parked far right. The editor drew a
       normal tidy graph and ignored every value.
    2. Moved nodes BY HAND in the editor and saved the scene. The
       saved file still held the exact values the script had written.
       Nothing was written back.

  So the editor neither reads nor writes that attribute. Node layout
  lives in the editor's own view data - the saved file carries
  "net.maxon.mvp.serializationV2_0.data.graph" and friends, an opaque
  MVP blob with no public Python API. "net.maxon.ui.position" is just
  a spare attribute slot that happens to accept a value.

### Removed

- All of it - WRITE_NODE_POSITIONS, NODE_POSITION_ATTR, the COL_* /
  ROW_HEIGHT grid, GraphBuilder.set_position() and every call to it.
  It was writing attributes nobody reads into every node of every
  material.

### Changed - And This Is The Part That Actually Improves The Layout

- The Size reroutes are now a FAN, not a chain. Every reroute hangs
  directly off the Size node instead of off the previous reroute.

  The node editor lays out by dependency depth - that is why the
  graph comes out in clean columns (Texture, TriPlanar, CC/Ramp/Bump,
  Standard Material, Blender, Output). A CHAIN of reroutes gives each
  one a different depth, so they marched diagonally down and to the
  right - the staircase. A FAN puts all of them at the same depth, so
  the editor drops them into a single column of their own, sitting
  right before the TriPlanars, with their wires running straight
  across into Scale.

  Working with the auto-layout instead of against it is the only
  lever there is, and it is the one that gets close to the
  right-angle look.

---

## v1.6 — 2026-09-10

### Fixed

- The "Size:" label in the dialog showed as "..." and only revealed
  itself in the tooltip. AddStaticText had a fixed initw of 40, which
  is narrower than the string, so C4D clipped it. initw is now 0,
  which sizes the gadget to its text.

### Not fixed - And Here Is What Is Actually Going On

- Node positions cannot be set from Python in this build, so the
  reroutes cannot be placed to give 90-degree wires. What you see in
  the node editor is Cinema 4D's own automatic arrangement, not this
  script's layout grid.

  The investigation, so it does not have to be repeated:
    - "net.maxon.ui.position" IS the right attribute id. Saving a
      scene and scanning it for position-related strings turns up
      that id and nothing else.
    - The value written is stored on the node and survives a save -
      it reads back correctly through GetValue.
    - The editor ignores it. Proof: "RS Standard" and "Output" are
      both written at y=0 and the editor still draws them at
      different heights.
    - The likely cause is the value TYPE. maxon.Vector is a 3-part
      Vector64; the editor probably wants a 2D vector, and the
      Python API exposes no 2D vector type at all (no Vector2d,
      Vec2d, Vec2f - only Vec3/Vec4 families).
    - Reroute nodes get no say either. The editor drops them along
      the wire it is drawing, which is why the Size bus comes out as
      a diagonal staircase.

  What DOES influence the result is build order - the graph is built
  one channel at a time (v1.5), which is why each channel's nodes now
  sit together in a row instead of interleaved.

  To settle the type question: open a generated material in the Node
  Editor, drag any node somewhere, save the scene. The editor will
  then write its own position value, and reading that value back
  reveals the exact type it expects. After that this layout grid can
  be switched on properly.

---

## v1.5 — 2026-09-10 (graph organisation)

### Added

- Reroute nodes on the Size wire. The shared "Size" node no longer
  fans out six long wires across the whole graph. It feeds a chain of
  reroutes - one per channel, named "Size BaseColor", "Size Roughness"
  and so on - and each reroute both drives its own TriPlanar's Scale
  and passes the value down to the next. Reroutes are plain wire
  carriers (net.maxon.node.reroute), not Redshift nodes, so they cost
  nothing at render time. If a build cannot create them the Size node
  wires straight into each Scale as before.
  New `GraphBuilder.add_reroute()`, `reroute_in()`, `reroute_out()`
  and `connect_ports()` - reroute ports are named plain "in"/"out" and
  are not addressable through the Redshift id scheme.
- Best-effort node placement. A layout grid (COL_* / ROW_HEIGHT) puts
  Size and its reroutes on the left, then one row per channel running
  Texture -> TriPlanar -> [Splitter] -> CC/Ramp/Bump/Displacement ->
  Standard Material -> Material Blender -> Output, with the Curvature
  chain parked below the last channel row.

  READ THIS IF THE LAYOUT DOES NOT TAKE: Cinema 4D does not publish
  the node editor's position attribute in the Python API - a freshly
  created graph carries no position data at all, because the editor
  arranges unplaced nodes itself. NODE_POSITION_ATTR is the id the
  editor is believed to use, but it could not be verified from
  script. If your build ignores it, nothing breaks - the editor just
  auto-arranges as before. Set WRITE_NODE_POSITIONS = False to stop
  writing it.

### Changed

- Materials are built channel by channel instead of layer by layer.
  v1.4 created every Texture Sampler, then every TriPlanar, then every
  Splitter; v1.5 finishes one channel before starting the next. Same
  graph, but the node editor's own automatic arrangement groups each
  channel together instead of interleaving them - which is what makes
  the difference when the position attribute above is not honoured.
- Dialog: the Size field now sits under the Triplanar checkbox rather
  than beside it.

      [ ] Triplanar
            Size: [0.01]
      [ ] Curvature

---

## v1.4 — 2026-09-10 (simplification pass on v1.3, all requested)

### Changed

- Triplanar size is ONE node again. v1.3 built
  SIZE -> Reciprocal -> Vector Maker -> every triplanar.scale so the
  dialog could speak in scene units. That chain is gone: a scalar
  connects directly into triplanar.scale and broadcasts to x/y/z, so
  the graph is now

      "Size" (Scalar Constant, 0.01) -> every TriPlanar's Scale

  The value is Redshift's own scale, default 0.01 - smaller number,
  bigger texture. One node, one number, nothing in between.
- "Dirt" is called Curvature everywhere - the checkbox, the option
  key and the node names ("Curvature", "Curvature Intensity",
  "Curvature Mask", "Curvature Texture", "Curvature CC",
  "Curvature Blender", "Blend Material").

### Removed From The Dialog

- Triplanar "Blend" field. The TriPlanar blend stays on the Redshift
  default and is tuned in the node.
- Curvature "Intensity" and "Radius" fields. Both stay on their node
  defaults - the Mul's Input 2 and the Curvature node's Radius are
  where you set them.
- The "Dirt Map" path field and its Browse button. The
  "Curvature Texture" sampler is always created empty, ready for
  whatever map you drop in.

  The dialog is now just: [ ] Triplanar  Size: [0.01]   [ ] Curvature

- The empty-texture note moved from the summary dialog to a console
  print. The texture being empty is the intended design now, so it
  is a breadcrumb rather than a warning: an unassigned Redshift
  texture sampler outputs black, and black x anything is black, so
  the curvature mask reads zero until a map is loaded into it.

    UNCHANGED
- Every texture channel, Displacement included, still gets its own
  TriPlanar and is still driven by the shared Size node.

---

## v1.3 — 2026-09-10 (Triplanar and the Curvature dirt blend, built on the v1.2 refactor)

### Added

- Triplanar. New "Triplanar" checkbox with a Size and a Blend field.
  When on, every texture channel - BaseColor, Roughness, Normal,
  Displacement, Opacity, Metalness - gets a TriPlanar node inserted
  between its Texture Sampler and whatever consumed it before.
  The TriPlanar's "Same Image On Each Axis" switch is used, so one
  wire per channel instead of three; if a Redshift build does not
  expose that switch, Image Y and Image Z are wired by hand instead.

  All six TriPlanar scales are driven by ONE node chain, so retiling
  the whole material means editing a single number:

      SIZE (Scalar Constant)
        -> "Size to Scale" (Reciprocal)
          -> "Triplanar Scale" (Vector Maker, x/y/z)
            -> every TriPlanar's Scale

  The Reciprocal is there on purpose. triplanar.scale scales the
  projection COORDINATES, so a small scale gives a big texture -
  the inverse of what "size" means to anyone using it. Inverting it
  once lets SIZE hold real scene units: 100 = one tile per 100
  units, and bigger number = bigger texture, which is what the field
  in the dialog says.

  Triplanar defaults to OFF. It ignores UVs completely, so switching
  it on for a model with baked UVs would quietly destroy the look.
  Note it costs three texture lookups per map: with six channels
  that is 18 lookups per shading point.

- Curvature dirt blend. New "Dirt (Curvature)" checkbox with
  Intensity and Radius fields and an optional Dirt Map file field.
  When on:

      Curvature -> Mul ("Dirt Intensity", input2 = the float)
                -> Mul ("Dirt Mask", input2 = Color Correct
                        <- "Dirt Map" Texture Sampler)
                -> Material Blender, Blend Color 1

      StandardMaterial (the folder's textures) -> blender Base Color
      "Dirt Material" (generated)              -> blender Layer 1
      Material Blender                         -> Output, Surface

  The generated dirt material is a plain StandardMaterial - dark
  brown base colour, roughness 0.85, metalness 0.
  Displacement still goes straight to Output.displacement; the
  blender only takes over the surface.

### Fixed / Worth Knowing

- Re-routing the surface output needs an explicit disconnect first.
  Connecting a second source to an input in a maxon graph does NOT
  replace the existing wire - both survive - so the default
  StandardMaterial -> Output.surface connection is removed via
  GraphModelHelper.RemoveConnection before the Material Blender is
  wired in. New `GraphBuilder.disconnect()`.
- The Dirt Map texture node is created empty by design, so any map
  can be dropped in later. An unassigned Redshift Texture Sampler
  outputs black, and black x anything is black, so the dirt mask
  reads zero until a map is loaded. The run now warns about this
  explicitly rather than leaving a correct-looking graph that
  renders nothing. Setting a path in the "Dirt Map" field avoids it.
- Identical warnings are collapsed with an "(xN)" count in the
  summary instead of repeating once per material.

### Known limitations

- The Curvature node is left on its Redshift default mode. If the
  dirt lands on the exposed edges rather than in the crevices,
  flip the Curvature node's Mode - the tool does not choose for you.

---

## v1.2 — 2026-09-10 (step 0: internal refactor, no change to the finished material)

### Added

- `GraphBuilder` - a thin wrapper around one Redshift node graph.
  `add()`, `connect()`, `set_value()`, `set_texture()` and
  `find_single()` take SHORT node/port ids ("bumpmap.out") and expand
  them against RS_NODE_PREFIX, so the long
  "com.redshift3d.redshift4c4d.nodes.core..." string appears once in
  the file instead of ~60 times.
- Missing nodes and ports are now REPORTED. v1.1 used
  `a and b and a.Connect(b)`, which produced a material with a silently
  missing wire. Every failure is appended to `GraphBuilder.warnings`,
  printed to the console, and shown in a summary dialog at the end of
  the run together with the created/failed counts.
- Port lookup falls back to a suffix match (via the existing
  `find_port`) when the exact id is absent, so a port renamed in a
  future Redshift build degrades to a warning instead of a broken
  material.
- Nodes are named in the node editor ("BaseColor Tex", "Roughness
  Ramp", "Normal Bump", ...). Cosmetic, but the graphs get crowded
  once Triplanar and the dirt blend are added.

### Changed

- `create_redshift_material()` rebuilt around a `chain` dict:
  `chain[channel]` holds the (node, output-port) pair that is currently
  the end of that channel's signal path. Each step wires from it and
  overwrites it. Inserting a node mid-chain - which is exactly what
  Triplanar needs - is now three lines instead of a new copy of the
  whole branch. The function went from ~330 lines to ~150.
- The per-channel colorspace map, the channel list and the Game Asset
  split channels moved to module-level tables (`CHANNEL_COLORSPACES`,
  `MATERIAL_CHANNELS`, `GAME_ASSET_SPLIT_CHANNELS`). Adding a channel
  is now a table entry plus one wiring block.
- The Game Asset ColorSplitter is applied in one generic pass over
  `GAME_ASSET_SPLIT_CHANNELS` rather than being duplicated inside the
  Roughness and Opacity branches.
- `create_redshift_material()` returns `(material, warnings)` instead
  of just the material. The only caller, `RedshiftMaterialImporterTool.run()`,
  collects them across the batch.
- The end-of-run dialog reports "Created N materials" plus any failures
  and warnings, instead of the fixed "Material creation process
  finished."

### Fixed

- `bumpmap.inputtype` was set with an unguarded
  `FindChild(...).SetDefaultValue(...)`, which raised AttributeError
  and aborted the whole material if that port was absent. It now goes
  through `set_value()` and degrades to a warning.
- A texture whose `tex0` port could not be resolved used to be skipped
  without any indication; it now warns with the file name.

### Not changed

- The resulting node graph is identical to v1.1 for every combination
  of channels, AO, Game Asset and Flip Green. Node names are the only
  visible difference.

---

## v1.1 — 2026-08-31
    Requested by the material team; all changes verified live in
    Cinema 4D 2025.3 against the `test tex` Substance exports.

### Added

- Normal map DirectX / OpenGL handling. New "Flip Green (DirectX)"
  checkbox, default ON. Substance Painter exports DirectX-convention
  normals, Redshift expects OpenGL - the two differ only in the sign
  of the Y (green) channel.
  Implemented in `apply_normal_flip()`. Primary path sets
  `...nodes.core.bumpmap.flipy` on the Bump Map node (confirmed
  present on 2025.3). If a Redshift build does not expose that port,
  it falls back to inverting green on the Texture Sampler via
  color_multiplier (1,-1,1) + color_offset (0,1,0), which is
  mathematically identical. If neither exists the material is still
  built and a warning is printed to the console.
  OFF leaves the normal untouched (OpenGL source).
- Subfolder scanning. The scan is now recursive, so selecting a parent
  folder picks up texture sets exported one-folder-per-material.
  There is deliberately NO checkbox for this - it is always on.
- Texture-extension whitelist (`TEXTURE_EXTENSIONS`), so Thumbs.db,
  .fbx and .obj files can no longer be mistaken for texture maps.
- "Metallic" added to the default Metalness keywords - Substance's
  actual export suffix, which the old "Metalness, Mtl" never matched.
- Preview dialog now reports which normal convention is in effect.

### Changed

- Material naming now preserves the full character name.
  `extract_identifier()` used to strip underscores and lowercase the
  filename BEFORE slicing, so "T_Wood_Planks_BaseColor.png" came out
  as "twoodplanks". It now matches on a separator-stripped, lowercased
  copy but slices the identifier out of the ORIGINAL string through an
  index map, giving "T_Wood_Planks". Both sides of the keyword are
  kept, so "T_Wood_Planks_BaseColor_2K.png" -> "T_Wood_Planks_2K".
  Grouping across channels uses `identifier_key()` (lowercased, no
  separators) so mixed spellings of the same set still land in one
  material, while the displayed name keeps its real capitalisation.
- BaseColor is now loaded as sRGB (RS_INPUT_COLORSPACE_SRGB). All
  other maps stay RAW. Previously every map including BaseColor was
  forced to RAW, which darkened albedo.
- Folder scanning moved out of `MyDialog` into the module-level
  `scan_folder()` / `build_material_name()`. Behaviour is unchanged;
  this removes the duplicated scan that Preview and Create each had,
  and makes the logic testable without opening the modal dialog.
- Model import now walks subfolders as well.

### Fixed

- Import 3D Model assigned the WRONG material. The assignment loop
  read a stale `ident` variable left over from the material-creation
  loop, so every imported object silently got the same material.
  Now: a single created material is applied to all imported objects;
  with several materials the one whose identifier appears in the
  object's name is used, and an object with no match is skipped with
  a console note rather than given an arbitrary material.
- Imported objects got Spherical texture projection, which stretched
  the maps across the model. A bare c4d.BaseTag(c4d.Ttexture) defaults
  to projection 0 (Spherical); texture tags now explicitly set
  TEXTURETAG_PROJECTION_UVW.
- Normal maps whose filename carries a format tag
  ("Wood_Normal_DirectX.png") were creating a second, duplicate
  material. DirectX/DX/OpenGL/OGL/GL tokens are now stripped from the
  identifier for the Normal channel only.
- Duplicate dialog gadget ID 9001 (used for both the "Material Name"
  static text and the button group). The button group is now 9010.

### Known limitations

- The AO checkbox inserts a PROCEDURAL Redshift ambient-occlusion
  node. It does not load an exported *_ambientocclusion.png map.
- Displacement is wired to the output but its scale is left at the
  Redshift default - it still needs tuning per asset.

---

## v1.0

Original tool: dialog-driven Redshift material creation with keyword matching
per channel, AO, Copy Textures, Game Asset (ColorSplitter) and Import 3D Model
options.
