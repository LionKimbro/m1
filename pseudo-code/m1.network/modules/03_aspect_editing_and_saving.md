```
date: 2026-08-20
title: Aspect editing and persistence for m1.network
target filename: src/m1/network/runtime.py
description: Changes the owning in-memory document and its network indexes together, then saves dirty files.
```

## OWNS

- Manipulating  entries, aspects on entries, tables.
- Determining the owning document for an edit and marking writable files dirty.
- Saving one dirty file or all dirty files (that is: outputting m1 transports).

## READS

- Runtime registers, selection, target file, and canonical-path convention.
  (As provided in: 01_runtime_state.md)
- The in-memory transport document held by each resource record.
  (As provided in: 01_runtime_state.md)

## CALLS

- `canonical_path()` for save targets.
- `refresh_document_table_before_save()` to embed the current local table view.
- UUID generation for new entities.
- JSON serialization and atomic filesystem replacement.
- `mark_file_dirty()`.

## MAY SAFELY ASSUME

- That the running process has authorized control of the files and directories required to operate.
  i.e. It is not necessary to re-read a file before writing to it, in order to see if there were changes since the last read.
- The importer has made each loaded entity-aspect pair correspond to exactly one source document.
- A target file either already has a writable resource record or can be initialized as an empty writable M1 transport document.
- Serializing an in-memory transport document cannot alter its represented JSON value.

## ENSURES

- An edit changes the source document and indexes as one logical operation.
- Editing an existing aspect preserves its established owner; target-file does
  not redirect it.
- Creating a new aspect records the selected target file as its owner.
- Only writable file resources enter `dirty_filepaths`.
- A successful save clears that file's dirty marker; a failed save leaves it
  dirty and preserves the last error information.

## DOES NOT OWN

- Importing a resource or resolving table locations.
- Constructing the save-time table projection; that cross-cutting policy belongs
  to the table-projection module.
- Merging edits with a changed external file.
- Writing URL resources.
- The semantic meaning or schema of aspect data.

## PSEUDOCODE

```python
def create_entity(flags=None):
    flags = flags or []
    owner = require_target_file_and_prepare_empty_document_if_needed()
    new_entity_id = generate_normalized_uuid()

    # A new entity has no aspects yet.  Give it a source-side representation so
    # later set_aspect() can edit the same document without special ownership.
    add_empty_entity_to_document(resources[owner]["data"], new_entity_id)
    aspects[new_entity_id] = {}
    sources[new_entity_id] = {}
    mark_file_dirty(owner)

    if "select" in flags:
        select_entity(new_entity_id)

    return new_entity_id


def set_aspect(a_id, data):
    selected_entity = require_selected_entity()
    require_json_compatible(data)

    if a_id in aspects[selected_entity]:
        owner = sources[selected_entity][a_id]
    else:
        owner = require_target_file_and_prepare_empty_document_if_needed()

    require_writable_file_resource(owner)
    replace_or_add_aspect_in_document(resources[owner]["data"], selected_entity, a_id, data)
    aspects[selected_entity][a_id] = data
    sources[selected_entity][a_id] = owner
    mark_file_dirty(owner)


def delete_aspect(a_id):
    selected_entity = require_selected_entity()
    if a_id not in aspects[selected_entity]:
        raise UnknownAspectError(selected_entity, a_id)

    owner = sources[selected_entity][a_id]
    require_writable_file_resource(owner)
    remove_aspect_from_document(resources[owner]["data"], selected_entity, a_id)
    del aspects[selected_entity][a_id]
    del sources[selected_entity][a_id]
    mark_file_dirty(owner)


def mark_file_dirty(canonical_filepath):
    resources[canonical_filepath]["dirty"] = True
    dirty_filepaths.add(canonical_filepath)


def save_file(p):
    filepath = canonical_path(p, ["new"])
    record = resources.get(str(filepath))
    if record is None or not record["dirty"]:
        return False

    refresh_document_table_before_save(record["data"])
    atomically_write_json(filepath, record["data"])
    record["dirty"] = False
    dirty_filepaths.discard(str(filepath))
    return True


def save_files():
    for filepath in list(dirty_filepaths):
        save_file(filepath)
```

## NOTES

- This module is intentionally strict about existing aspects: their provenance
  decides the write destination, even if another target file is selected.
- Whether an empty entity must be serialized before it has an aspect is a
  transport-envelope question. The function shows the necessary ownership
  behavior but leaves the exact representation for the envelope module.
- `atomically_write_json()` should write a sibling temporary file and replace
  the destination only after serialization succeeds; its detailed failure and
  recovery policy deserves a later bounded sketch.
