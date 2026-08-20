```
title: m1.network API documentation
date: 2026-08-20
audience: Agents writing code against m1.network
```

# m1.network

`m1.network` is an in-memory M1 transport network with a single owner for
each loaded entity-aspect pair.  Use it when a program needs to import M1 v3
transport documents, inspect their loaded aspects, make local edits, and save
only the documents made dirty by those edits.

Import it as:

```python
import m1.network as m1
```

Use `m1` as the normal local name.  If the same file also needs the legacy
top-level `m1` facade, choose a distinguishing local name such as `network`,
`m1n`, or use the fully qualified module name instead.

The module is a stateful machine.  It owns one process-wide network, exposed
through its public registers.  It is not a general-purpose immutable document
parser, nor does it merge conflicting aspect values.

## Start of a flow

Call `reset_runtime()` before an isolated operation or test that
requires an empty network.  It clears the network in place and returns `g`.

```python
m1.reset_runtime()
```

Do not reset a network that another part of the process is using.

## M1 model and import rule

An imported document must be an M1 v3 transport object.  Its `m1` header must
have a lowercase hyphenated UUID `id`, `version: "3.0"`, and an ISO-8601
`timestamp`.  An optional `series_id` is also a lowercase hyphenated UUID.

Entity and aspect identifiers must be either lowercase hyphenated UUIDs or
Tag URI strings.  Tag URIs are preserved exactly.  Aspect values must be JSON
compatible, including `null`.  The runtime preserves unknown aspect IDs and
their JSON values.

The v3 transport tombstone keys are validated and preserved in the source
document, but this runtime's loaded-aspect index contains only contributed
aspects.  In particular, it does not implement a layered tombstone view.

An import is atomic.  If a file cannot be read, parsed, or validated, it adds
no entities or aspects.  If *any* entity-aspect pair in a valid document is
already loaded, the whole document is rejected; matching values are not
silently merged.

```python
info = m1.import_file("data/people.m1")
info = m1.import_url("https://example.net/people.m1")
```

Each successful import returns:

```python
{"document-key": "...", "entity-aspects": 3}
```

For files, the document key is its canonical absolute path string.  For URLs,
it is the supplied URL string.

Import raises `ResourceReadOrValidationError` for an unreadable, invalid JSON,
or invalid M1 v3 document, and `RedefinedEntityAspectError` when it would
redefine a loaded entity-aspect pair.  Failed and rejected resource records
remain inspectable in `resources` unless that key already names a successfully
loaded resource.

## Selection and reading

The selection register is the current entity for aspect operations.

```python
m1.select_entity(entity_id)
aspect_ids = m1.known_aspects()
value = m1.get_aspect(m1.BASIC_ASPECT)
```

`known_entities()` returns all currently known entity IDs in insertion order.
`known_aspects()` returns the selected entity's loaded aspect IDs in insertion
order.  `get_aspect()` returns a deep copy, so changing the returned value does
not change the network.

`select_entity()` raises `UnknownEntityError` for an unknown ID.
`known_aspects()` and `get_aspect()` raise `NoSelectedEntityError` when no
entity is selected.  `get_aspect()` and `delete_aspect()` raise
`UnknownAspectError` when the selected entity lacks the requested aspect.

## Creating and editing

Set a target file before creating an entity or adding an aspect that has no
existing owner:

```python
m1.target_file("data/my-edits.m1")
entity_id = m1.create_entity(["select"])
m1.set_aspect(m1.BASIC_ASPECT, {"title": "A new entity"})
m1.save_files()
```

`target_file(path)` canonicalizes the supplied path.  The file itself may be
new, but its parent directory must already exist.

`create_entity()` creates an entity with no aspects in the target document and
returns its new lowercase UUID.  Its optional `select` flag selects that new
entity.  Calling it without a target file raises `NoTargetFileError`.

`set_aspect(aspect_id, data)` changes the selected entity.  The value must be
JSON compatible.  If the aspect already exists, its established source
document remains its owner, regardless of the current target file.  Otherwise
the current target file becomes the owner.  `delete_aspect(aspect_id)` removes
the aspect from its owning document and from the runtime indexes.

Edits are allowed only to writable file resources.  URL resources are
read-only and cause `UnwritableResourceError` when selected as an existing
aspect owner.

## Saving

`save_file(path)` writes one dirty canonical file resource atomically and
returns `True`; it returns `False` when that resource is absent or clean.
`save_files()` saves every dirty file and returns the canonical paths that were
saved.

Every successful save emits a fresh `m1.id` and fresh `m1.timestamp`.  The
document's `series_id` is preserved.  A document that did not yet have a
`series_id` receives a new UUID on its first save, and later saves preserve it.
The dirty marker is cleared only after the atomic replacement succeeds.

Immediately before serialization, saving replaces the document's `table` with
a current local projection.  It includes known locations only for entities
with aspect definitions in that document and, for each stored link aspect,
its direct `from` and `to` endpoints.  An empty entity record does not cause a
table entry.  The projection omits IDs without locations and does not traverse
beyond those direct endpoints.  This is an advertisement of the runtime's
current knowledge, not an authoritative table merge or location-selection
policy.

## Loading more from table locations

Imported documents may contribute table entries of these forms:

```python
{"type": "file", "path": "C:/data/next.m1"}
{"type": "url", "url": "https://example.net/next.m1"}
```

`load_more(flags=None)` attempts eligible entries in table insertion order.
It catches individual import failures and continues with later entries.  It
returns per-call information:

```python
{
    "complete": True,
    "attempted": 2,
    "files": {"loaded": 1, "rejected": 0, "failed": 1},
    "urls": {"loaded": 0, "rejected": 0, "failed": 0},
}
```

Supported flags are:

- `entity` — load locations for the selected entity; this is the default.
- `all` — load every table entry, in table and entry insertion order.
- `repeat` — make further ordered passes to discover locations added by
  successful imports in the same call.
- `retry-rejected` — retry entries whose last result was `REJECTED`.
- `retry-failed` — retry entries whose last result was `FAILED`.

`all` and `entity` are mutually exclusive.  Without either retry flag,
previously failed and rejected entries are skipped; successfully loaded entries
are always skipped.  A repeated call never retries the same document key more
than once within that call.

Set `g["load-more-max-files"]` to a positive integer or `None`, and
`g["load-more-stop-after-seconds"]` to a non-negative number or `None`, to
control a call.  The count is locations attempted, not successful imports.
`None` disables only its corresponding limit.  `g["load-more-complete"]` is
`False` if a limit stopped the call and `True` when its requested scope reached
the current stopping point.

The related last-call metrics live in `g` under `load-more-attempted` and
`load-more-{files|urls}-{loaded|rejected|failed}`.

## Public state registers

The following registers are intentionally public for inspection and machine
control.  Mutate them only when the API explicitly documents that use.

- `aspects`: `{entity_id: {aspect_id: data}}`, the current loaded view.
- `sources`: `{entity_id: {aspect_id: document_key}}`, ownership provenance.
- `resources`: `{document_key: record}`, source documents and load state.
- `table`: `{entity_id: [table_entry, ...]}`, accumulated table locations.
- `dirty_filepaths`: canonical path strings awaiting save.
- `g`: selection, target, loading policy, result, error, and metric facts.

For normal application behavior, use the API rather than directly changing
`aspects`, `sources`, `resources`, `table`, or `dirty_filepaths`; direct edits
can break the import/edit atomicity invariant.  The intentional configuration
exceptions are the two `load-more-*` policy values in `g`.

## Constants

```python
m1.BASIC_ASPECT  # tag:m1lattice.net,2026:aspect/basic
m1.LINK_ASPECT   # tag:m1lattice.net,2026:aspect/link
m1.LOG_ASPECT    # tag:m1lattice.net,2026:aspect/log
```

These are conventions, not a closed aspect schema.  A program may write other
valid M1 aspect identifiers when its domain needs them.
