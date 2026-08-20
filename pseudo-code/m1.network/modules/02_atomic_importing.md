```
date: 2026-08-20
title: Atomic resource importing for m1.network
target filename: src/m1/network/runtime.py
description: Loads one M1 transport document and joins its entity-aspect data atomically.
```

## OWNS

- Loading a file or URL resource into a staged document record.
- Validating a transport document sufficiently to protect the runtime indexes.
- Rejecting a resource that redefines an already-known entity-aspect pair.
- Committing an accepted document's entities, aspects, provenance, and resource
  record together.

## READS

- Runtime registers from the state module.
- File contents or URL response bodies.
- Existing entity-aspect ownership in `aspects` and `sources`.

## CALLS

- `_canonical_path()` for file resource keys.
- A JSON parser and URL reader.
- UUID normalization and entity-ID validation helpers.
- `_record_entry()` if the table is populated from imported metadata.

## MAY SAFELY ASSUME

- The runtime registers satisfy the state module's invariants before an import.
- A caller supplies either a file path or URL, never an already-decoded document.
- The core M1 specification permits unknown aspect IDs and any JSON value,
  including `null`.

## ENSURES

- An accepted document joins completely: each of its entity-aspect pairs is in
  `aspects`, and each pair has provenance in `sources`.
- A failed or rejected import changes neither the network indexes nor existing
  resource records.
- A readable document that redefines any loaded entity-aspect pair is recorded
  as `REJECTED` and does not join at all.
- A failed read, JSON parse, or structural validation is recorded as `FAILED`.

## DOES NOT OWN

- Choosing which table locations `load_more()` should attempt.
- Resolving disagreements between valid sources; conflicting pairs are simply
  rejected at this runtime boundary.
- Editing or saving any imported document.
- Aspect-specific validation beyond the transport shape and JSON compatibility.

## PSEUDOCODE

```python
def import_file(p):
    filepath = _canonical_path(p)
    source = {"type": "file", "path": str(filepath)}
    return _load_resource(source, document_key=str(filepath))


def import_url(url):
    source = {"type": "url", "url": url}
    return _load_resource(source, document_key=url)


def _load_resource(source, document_key):
    staged_record = {
        "source": source,
        "data": None,
        "dirty": False,
        "writable": source["type"] == "file",
        "load_attempted": now(),
        "load_result": None,
    }

    try:
        staged_record["data"] = _read_and_parse_transport_document(source)
        staged_pairs = _validate_and_normalize_document(staged_record["data"])
    except ResourceReadOrValidationError as error:
        staged_record["load_result"] = "FAILED"
        staged_record["load-error-info"] = error.info
        resources[document_key] = staged_record
        raise

    if _has_entity_aspect_pair_already_loaded(staged_pairs):
        staged_record["load_result"] = "REJECTED"
        resources[document_key] = staged_record
        raise RedefinedEntityAspectError(document_key)

    staged_record["load_result"] = "LOADED"
    _commit_entire_validated_document(staged_pairs, document_key, staged_record)
    return _make_import_info_for_resource(document_key, staged_pairs)


def _has_entity_aspect_pair_already_loaded(staged_pairs):
    for e_id, a_id, data in staged_pairs:
        if e_id in aspects and a_id in aspects[e_id]:
            return True
    return False


def _commit_entire_validated_document(staged_pairs, document_key, staged_record):
    # All rejection points occur before this procedure.  Its operations cannot
    # fail under the stated assumptions, so the network is never half-joined.
    resources[document_key] = staged_record
    for e_id, a_id, data in staged_pairs:
        aspects.setdefault(e_id, {})[a_id] = data
        sources.setdefault(e_id, {})[a_id] = document_key
```

## NOTES

- A rejected resource is retained in `resources` for diagnostics but never
  becomes an owner in `sources` or a value in `aspects`.
- Staging is deliberately local, rather than an alternate global index, to keep
  the commit boundary obvious.
- The exact transport-document envelope remains an unresolved detail. Its
  validator belongs in this target file but should be specified in a later,
  narrower module before implementation.
