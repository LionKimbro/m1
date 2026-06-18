# M1 Runtime Manual

This document explains how to use the `m1` Python package as a runtime for loading, inspecting, editing, and re-emitting M1 data.

It is about programmer use of the runtime module. It does not describe the browser UI.

## What The Runtime Is

The M1 runtime does two things at once:

1. It preserves all loaded M1 transport documents in memory.
2. It gives you a selected current view of entity/aspect data.

These are both important.

The runtime preserves all loaded claims by keeping all loaded M1 documents in memory. It also provides a simple programmer-facing access pattern: for a targeted entity, ask for an aspect and get the currently visible value.

This means the runtime is not just a serializer, and not just a database. It is a layered session model with:

- a writable session layer called the overlay
- zero or more loaded M1 documents
- a priority order among those loaded M1 documents
- a cache of selected visible values

## The Core Mental Model

When you ask for an aspect on an entity, the runtime searches in this order:

1. overlay
2. highest-priority loaded M1 document
3. next loaded M1 document
4. and so on

The first value found wins.

If that value is `None`, that also wins.

`None` is not treated as "not found." It is a real tombstone value meaning:

"This aspect on this entity is explicitly absent."

Once `None` is encountered, lower-priority M1 documents are not consulted for that aspect.

M1 also defines a conventional whole-entity tombstone aspect:

```text
tag:m1lattice.net,2026/aspect/tombstone
```

An active value such as `{"entity": true}` establishes an entity-wide cutoff. The tombstone's own layer and lower-priority layers do not contribute visible aspects for that entity. Higher-priority layers may still reintroduce it.

## The Runtime Data Structures

The runtime keeps several global structures.

### `overlay`

This holds the entity/aspect edits made during the current session.

Conceptually:

```python
overlay = {
    entity_id: {
        aspect_id: aspect_data_or_none,
    },
}
```

`set_aspect(...)` writes here.

### `overlay_headers`

This holds the intended M1 header values for the next emitted document.

Conceptually:

```python
overlay_headers = {
    "id": "...optional intended UUID...",
    "series_id": "...optional...",
    "created": "...optional...",
    "author": "...optional...",
    "title": "...optional...",
    "description": "...optional...",
    "hook": "...optional...",
}
```

These values are used when saving. On amend saves, unspecified header values do not erase what is already present in the target file.

### `overlay_table`

This holds session table contributions.

Table entries are handled separately from entity/aspect data.

### `cache`

This holds the selected currently visible value for each `entity_id + aspect_id`.

Conceptually:

```python
cache = {
    entity_id: {
        aspect_id: aspect_data_or_none,
    },
}
```

This is a view, not the preservation layer.

### `source`

This records which loaded M1 document currently supplies the selected visible aspect value.

Conceptually:

```python
source = {
    entity_id: {
        aspect_id: m1_id,
    },
}
```

If the visible value comes from overlay, the effective source layer is overlay rather than a loaded M1 document.

### `table_cache`

This is the table equivalent of `cache`.

It holds the selected visible table entries by identifier.

### `M1`

This preserves all loaded M1 documents.

Conceptually:

```python
M1 = {
    m1_id: m1_document,
}
```

This is the main claim-preserving structure.

### `M1_loaded_from`

This maps loaded M1 document UUID to the path it was loaded from.

Conceptually:

```python
M1_loaded_from = {
    m1_id: path,
}
```

This is load provenance, not an eternal home. The same path may hold different transport UUIDs over time.

### `priority`

This is the ordered list of loaded M1 document UUIDs consulted after overlay.

Higher priority means earlier consultation.

## M1 Transport Identity

Each emitted M1 transport document has a header under `m1`.

Important fields:

- `m1.id`
- `m1.series_id`
- `m1.created`
- `m1.timestamp`

Meaning:

- `m1.id`: UUID of this specific emitted transport artifact
- `m1.series_id`: optional UUID for the ongoing series or lineage
- `m1.created`: optional timestamp for when the series was created
- `m1.timestamp`: timestamp for this specific emission

The runtime uses a publish-once model for `m1.id`.

If content changes and you emit again, the new emission must get:

- a new `m1.id`
- a new `m1.timestamp`

The old and new emitted documents may have the same `m1.series_id`.

## Basic Access Pattern

The runtime uses a targeted-entity style.

Typical use:

```python
import m1

m1.load_m1("background.m1")
m1.load_m1("working-file.m1")

m1_basic = "tag:m1lattice.net,2026/aspect/basic"

m1.target_entity("7c2be3c4-1111-4d54-b432-aaaaaaaaaaaa")
basic = m1.get_aspect(m1_basic)
```

You first set the target entity, then ask for aspects on it.

## The Main Functions

### Targeting

```python
m1.target_entity(entity_id)
m1.get_entity()
m1.clear_target()
```

Use `target_entity(...)` before calling entity-local functions such as `get_aspect(...)`, `set_aspect(...)`, `list_aspects(...)`, and `source_aspect(...)`.

### Reading Aspects

```python
m1.get_aspect(aspect_id)
m1.has_aspect(aspect_id)
m1.has_aspect(aspect_id, "*")
m1.list_aspects()
m1.list_aspects("*")
m1.get_surface()
m1.get_surface("*")
```

Notes:

- `get_aspect(...)` returns the selected visible value
- that value may legitimately be `None`
- `list_aspects()` excludes tombstoned aspects
- `list_aspects("*")` includes aspects whose visible value is `None`
- `get_surface()` returns a dictionary of visible non-`None` aspects
- `get_surface("*")` includes tombstones

### Writing Aspects

```python
m1.set_aspect(aspect_id, aspect_data)
```

This writes directly into overlay on the currently targeted entity.

Important behaviors:

- `aspect_data` may be `None`
- writing `None` creates a tombstone
- `set_aspect(...)` immediately updates the selected cache
- `set_aspect(...)` immediately updates the selected aspect source
- `set_aspect(...)` clears any previously intended emitted `m1.id` in `overlay_headers`

That last rule matters because changing overlay content means the next emitted document should normally get a fresh UUID.

Example:

```python
m1_basic = "tag:m1lattice.net,2026/aspect/basic"

m1.target_entity(project_id)
m1.set_aspect(m1_basic, {
    "title": "M1",
    "tags": ["program", "knowledge-system"],
})

m1.set_aspect("tag:example.org,2026:aspect/obsolete-note", None)
```

### Tombstoning A Whole Entity

The intended convenience API is:

```python
m1.target_entity(entity_id)
m1.tombstone_entity({
    "reason": "Removed from this layered view."
})
```

This writes the conventional aspect:

```json
{
  "tag:m1lattice.net,2026/aspect/tombstone": {
    "entity": true,
    "reason": "Removed from this layered view."
  }
}
```

The same result may be expressed directly with `set_aspect(...)`.

An entity tombstone:

- covers all ordinary aspects in its own layer and lower-priority layers
- does not cover higher-priority contributions
- does not destroy the UUID
- does not invalidate links or other references
- is not the same as omitting the UUID from a saved transport

Snapshot saving must retain the selected tombstone aspect while excluding the ordinary aspects it covers. Merely leaving the UUID out would lose the explicit absence assertion and could allow lower layers to reappear when the snapshot is loaded with other data.

The current Python implementation predates this specification amendment and does not yet apply entity-wide tombstone selection semantics.

### Listing Entities

```python
m1.list_entities()
m1.has_entity(entity_id)
```

These operate on the total visible entity surface.

### Sourcing

```python
m1.source_aspect(aspect_id)
m1.loaded_from(m1_id)
```

Use these when you want provenance.

- `source_aspect(...)` tells you which loaded M1 document currently supplies the visible aspect value
- `loaded_from(...)` tells you where a loaded M1 document came from

Example:

```python
m1_basic = "tag:m1lattice.net,2026/aspect/basic"

m1.target_entity(project_id)
src = m1.source_aspect(m1_basic)
path = None if src is None else m1.loaded_from(src)
```

If the visible value is coming from overlay, `source_aspect(...)` returns `None`.

### Loaded M1 Documents

```python
m1.list_m1()
m1.get_m1(m1_id)
m1.has_m1(m1_id)
m1.drop_m1(m1_id)
m1.drop_m1("all")
```

Use these when you want to manage the loaded M1 document set itself.

`drop_m1("all")` clears all loaded M1 documents while preserving overlay.

### Ordering

```python
m1.list_priority()
m1.order("ts")
m1.order("ts", "-")
m1.order("load-order")
m1.order([uuid1, uuid2, uuid3])
```

Ordering affects which loaded M1 document wins when multiple documents say something about the same entity/aspect.

Changing priority clears the selected cache and selected source views, which are then recomputed on demand or by `refresh()`.

### Cache And Rebuild

```python
m1.clear_cache()
m1.clear_cache(m1_id)
m1.clear_cache("overlay")
m1.refresh()
```

Use:

- `clear_cache()` to clear all selected aspect and table cache state
- `clear_cache(m1_id)` to clear only those cached entries touched by a specific loaded M1 document
- `clear_cache("overlay")` to clear only those cached entries touched by overlay
- `refresh()` to rebuild selected views from current runtime state

## Header Helpers

The runtime provides helpers for setting M1 header intent before saving.

```python
m1.get_headers()
m1.set_uuid(uuid)
m1.stamp_creation()
m1.set_author(author)
m1.set_title(title)
m1.set_description(description)
m1.set_hook(hook)
m1.set_headers({...})
```

These manipulate `overlay_headers`.

Typical use:

```python
m1.set_title("Programming Language Notes")
m1.set_author("Lion Kimbro")
m1.stamp_creation()
```

### About `set_uuid(...)`

Normally, when a document is emitted, it gets a fresh UUID.

If you need the emitted document to refer to itself, you may explicitly set the intended UUID before save:

```python
m1.set_uuid("5f4e9b8e-1111-4f7c-91d5-bbbbbbbbbbbb")
```

That UUID is treated as intended header content for the next emission.

## Loading

### Basic Load

```python
m1.load_m1(path, flags="")
```

If you load without explicit `O` or `S`, the document is loaded into the loaded-document world and added to priority.

In ordinary use, that is what you want for background material and reference material.

### Load Targets

- `O`: load into overlay
- `S`: load as snapshot

### Load Actions

- `+`: additive load
- `!`: overwrite load
- `-`: safe load

### Other Load Flags

- `k`: keep existing state during load
- `t`: include table contributions
- `w`: weed table after load; requires `t`

### Overlay Loads

#### `O+`

Add loaded content into overlay.

`None` values are preserved as real tombstones.

#### `O!`

Replace overlay contents with the loaded document contents.

#### `O-`

Load into overlay only if overlay is empty.

### Snapshot Loads

#### `S!`

Replace the currently loaded world with the snapshot.

This rebuilds:

- `M1`
- `priority`
- `cache`
- `source`

If `k` is absent, overlay is cleared.

If `k` is present, overlay is preserved.

#### `S+`

Load the snapshot at highest priority while keeping everything else loaded.

#### `S-`

Only load the snapshot if no other M1 data has been loaded.

### Same-Path Reload Behavior

If you load from a path that is already represented in `M1_loaded_from`:

- without `k`: previously loaded documents from that path are removed first
- with `k`: previously loaded documents from that path are preserved

This means:

- without `k`, a successful load leaves at most one currently loaded document from that path
- with `k`, multiple loaded documents may coexist from the same path

## Saving

### Basic Save

```python
m1.save_m1(path, flags="")
```

The default save target is overlay.

### Save Targets

- `O`: save overlay only
- `S`: save snapshot of the total visible surface

### Save Actions

- `+`: amend save
- `!`: overwrite save
- `-`: safe save

### Other Save Flags

- `t`: include table contributions
- `w`: weed table before save; requires `t`

### Overlay Saves

#### `O!`

Write the current overlay as a new emitted M1 transport at the target path.

#### `O+`

If the target file exists:

1. load that file
2. amend its entity content with overlay
3. merge `overlay_headers` on top of its `m1` header
4. preserve unspecified existing header keys
5. emit fresh `m1.id`
6. emit fresh `m1.timestamp`
7. write result back

This is useful when you are progressively editing an M1 file and want to preserve material that was already there.

#### `O-`

Refuse to write if the target path already exists.

### Snapshot Saves

#### `S!`

Write the current visible world as a snapshot.

#### `S+`

Amend an existing file with the current visible world.

This preserves unspecified existing `m1` header keys, but still emits a fresh `m1.id` and a fresh `m1.timestamp`.

#### `S-`

Refuse to write if the target path already exists.

## The Meaning Of Tombstones

Tombstones are central to the runtime.

If you set:

```python
m1.set_aspect(aspect_id, None)
```

you are not saying:

"I don't know."

You are saying:

"This aspect on this entity is explicitly absent."

That explicit absence covers lower-priority definitions.

This applies both in runtime and in serialized transport, where `None` becomes JSON `null`.

For whole-entity absence, use the conventional entity tombstone aspect rather than setting every known aspect to `None`. Setting every known aspect to `None` cannot cover an unknown aspect that appears only in a lower layer.

An entity tombstone is positive information carried by the transport. By contrast, omitting an entity from a save emits no information about that UUID. These operations must remain distinct.

## Tables

M1 transport may contain a `table` section that maps identifiers to lists of location objects.

The runtime treats table data separately from entity/aspect data.

### Table Inclusion

Table data is only involved when you explicitly use the `t` flag on load or save.

Without `t`:

- load ignores the table
- save ignores the table

### Table Resolution

The runtime provides:

```python
m1.resolve_table(identifier)
```

This resolves the currently visible table entry list for an identifier, using overlay table first and then priority order.

### Weeding

The runtime provides:

```python
m1.weed_table()
```

This checks `file`-type entries in `overlay_table`, and removes those whose paths no longer exist.

The `w` flag applies weeding automatically:

- on load: after load
- on save: before save

`w` requires `t`.

## Common Working Pattern

The most common workflow is likely to be:

1. load background M1 files
2. load the file you are working from
3. target an entity
4. inspect aspects
5. call `set_aspect(...)` to write changes into overlay
6. set any desired header values
7. save with amend or overwrite behavior

Example:

```python
import time

import m1

m1.load_m1("F:/lion/github/m1/testdata/001__people-and-languages.m1")
m1.load_m1("F:/lion/github/m1/testdata/002__programs-and-links.m1")

PROJECT_ID = "b2c3d4e5-1111-49a0-8b01-555555555555"
M1_BASIC = "tag:m1lattice.net,2026/aspect/basic"
M1_LOG = "tag:m1lattice.net,2026/aspect/log"
MY_NOTES_ASPECT = "tag:lionkimbro@gmail.com,2026-05-07/aspect/notes"

m1.target_entity(PROJECT_ID)

basic = m1.get_aspect(M1_BASIC) or {}
log = m1.get_aspect(M1_LOG) or {"log": []}

print("Project:", basic.get("name"), "-", basic.get("title"))

log_entry = {}
log_entry["timestamp"] = str(time.time())
log_entry["event"] = "UPDATED"
log_entry["note"] = "demonstration update; setting a custom aspect"
log_entry["via"] = "example code"
log["log"].append(log_entry)

m1.set_aspect(M1_LOG, log)

m1.set_aspect(MY_NOTES_ASPECT, {
  "text": "Refactoring runtime around overlay and priority."
})

m1.set_title("M1 Working Notes")
m1.set_author("Lion Kimbro")

m1.save_m1("F:/lion/github/m1/out/working-notes.m1", "O!")
```

## Why This Runtime Is Useful

This runtime gives you a way to work with M1 that is:

- claim-preserving, because all loaded M1 documents are retained
- practical, because you can ask for the current visible value
- editable, because overlay is a first-class writable layer
- provenance-aware, because visible values can be sourced back to loaded M1 documents
- re-emittable, because overlay and snapshot saves are built in

In other words, it lets you work with M1 as a living session model rather than as a pile of JSON files.

## Related Documents

- [020__spec.json](F:\lion\github\m1\docs\raw\020__spec.json)
- [021__transport-spec.json](F:\lion\github\m1\docs\raw\021__transport-spec.json)
- [024__runtime-model-notes_2026-05-05.txt](F:\lion\github\m1\docs\raw\024__runtime-model-notes_2026-05-05.txt)
- [025__runtime-spec.json](F:\lion\github\m1\docs\raw\025__runtime-spec.json)
