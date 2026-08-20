```
date: 2026-08-20
title: Save-time table projection for m1.network
target filename: src/m1/network/runtime.py
description: Embeds current known locations only for entities mentioned by the document's aspects and direct link endpoints.
```

## OWNS

- Determining the entity IDs mentioned by a document's aspect definitions.
- Replacing that document's serialized table with a fresh projection of the
  runtime's current table knowledge for those IDs.
- Expanding coverage to direct `from` and `to` endpoints of link aspects
  defined in the document.

## READS

- The transport document about to be saved.
- `table` for the current known locations of each covered entity.

## CALLS

- No other m1.network module; `save_file()` invokes this module immediately
  before serialization.

## MAY SAFELY ASSUME

- The selected transport envelope has a defined entity enumeration and table
  field.
- A recognized link aspect has JSON-object data containing valid entity IDs in
  its required `from` and `to` fields.
- Location entries in `table` are already in the order in which this runtime
  wishes to advertise them.

## ENSURES

- Every entity with at least one aspect definition in the saved document is
  considered for table projection.
- For each link aspect definition in the saved document, its direct `from` and
  `to` endpoints are also considered, whether or not those endpoint entities
  have aspect definitions in the document.
- The saved document's table contains the runtime's current known location list
  for every covered ID that has at least one known location.
- No entity is included merely because it is known in the global `table` or
  `aspects` register.
- The projection is a replacement, not an incremental merge: stale advertised
  entries for covered IDs are removed.
- This refresh changes only the in-memory source document. The caller's normal
  atomic save operation remains responsible for durable replacement.

## DOES NOT OWN

- The global `table` itself, including discovery, merge, ordering, or resource
  selection policy.
- Recursive graph traversal beyond the direct endpoints of a link aspect
  definition in the document.
- The semantics of unknown aspects or of location types.
- Parsing imported document tables or loading their referenced resources.

## PSEUDOCODE

```python
def refresh_document_table_before_save(document):
    covered_entity_ids = set()

    for e_id, a_id, data in iter_aspect_definitions_from_document(document):
        covered_entity_ids.add(e_id)
        if a_id == LINK_ASPECT:
            link_data = data
            covered_entity_ids.add(link_data["from"])
            covered_entity_ids.add(link_data["to"])

    projected_table = {}
    for e_id in covered_entity_ids:
        if e_id in table and table[e_id]:
            projected_table[e_id] = copy_location_entries(table[e_id])

    replace_document_table(document, projected_table)


def copy_location_entries(entries):
    # Later changes to the runtime table must not mutate a document record.
    return deep_json_copy(entries)
```

## NOTES

- This mechanism says, “this is the best location knowledge I currently have
  for these IDs.” It does not claim global authority, freshness, or exclusivity.
- A link endpoint is included only one hop from a link aspect definition in the
  document. If an endpoint is itself a link entity but has no link aspect
  definition in the document, its endpoints are not added.
- IDs without known locations do not receive empty lists in the projected
  table. Their absence continues to mean that this runtime knows no location.
- An entity record with no aspect definitions does not cause a table entry. It
  has not been mentioned in the required sense.
- The final transport envelope, including the exact spelling and placement of
  its table field, remains a separate bounded specification question.
