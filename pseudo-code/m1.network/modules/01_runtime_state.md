```
date: 2026-08-20
title: Runtime state and selection for m1.network
target filename: src/m1/network/runtime.py
description: Establishes the in-memory M1 network registers and selected-entity context.
```

## OWNS

- Initialization and reset of the runtime registers: `aspects`, `sources`,
  `resources`, `table`, `dirty_filepaths`, and `g`.
- Canonical file-path handling used by this runtime.
- The selected entity and target file settings.
- Read-only accessors for entities and their loaded aspects.

## READS

- Entity and aspect indexes maintained by the import and editing modules.
- The filesystem only to canonicalize an existing path, or a new file's parent.

## CALLS

- `Path.resolve()` for filesystem-backed path canonicalization.
- No other m1.network module.

## MAY SAFELY ASSUME

- Python values held in `aspects` are JSON-compatible because the importer and
  editor validate them before committing a change.
- Callers select an entity before asking for that entity's aspects.

## ENSURES

- Every stored file path is canonical.
- `sources[e_id][a_id]` names the document which currently owns the matching
  loaded `aspects[e_id][a_id]` value.
- A selection is either `None` or an entity ID presently known in `aspects`.
- Accessors never mutate the network.

## DOES NOT OWN

- Reading transport documents or deciding whether a resource joins the network.
- Editing aspects or marking a document dirty.
- Serializing and saving documents.
- Interpreting the semantics of any aspect beyond the runtime's bookkeeping.

## PSEUDOCODE

```python
BASIC_ASPECT = "tag:m1lattice.net,2026:aspect/basic"
LINK_ASPECT = "tag:m1lattice.net,2026:aspect/link"
LOG_ASPECT = "tag:m1lattice.net,2026:aspect/log"


def _reset_network_runtime():
    # Called once at startup and by tests that need an empty network.
    aspects = {}
    sources = {}
    resources = {}
    table = {}
    dirty_filepaths = set()
    g = {
        "selected-entity": None,
        "target-file": None,
        "load-more-max-files": 10,
        "load-more-stop-after-seconds": 1,
        "load-more-complete": None,
    }


def _canonical_path(p, flags=None):
    flags = flags or []
    candidate = Path(p)

    if "new" in flags:
        resolved_parent = candidate.parent.resolve(strict=True)
        return resolved_parent / candidate.name

    return candidate.resolve(strict=True)


def target_file(p):
    g["target-file"] = _canonical_path(p, ["new"])
    return g["target-file"]


def select_entity(e_id):
    if e_id not in aspects:
        raise UnknownEntityError(e_id)

    g["selected-entity"] = e_id
    return e_id


def known_entities():
    return list(aspects.keys())


def known_aspects():
    selected_entity = _get_selected()
    return list(aspects[selected_entity].keys())


def get_aspect(a_id):
    selected_entity = _get_selected()

    if a_id not in aspects[selected_entity]:
        raise UnknownAspectError(selected_entity, a_id)

    return aspects[selected_entity][a_id]


def _get_selected():
    selected_entity = g["selected-entity"]
    if selected_entity is None:
        raise NoSelectedEntityError()

    return selected_entity
```

## NOTES

- `_reset_network_runtime()` creates all registers together so no partially
  initialized network is observable.
- The indexes deliberately retain insertion order; this gives a stable,
  unsurprising result for the list accessors without assigning semantic meaning
  to that order.
- This module uses normal reusable action and predicate-shaped function names;
  no callback entry points are defined here.
