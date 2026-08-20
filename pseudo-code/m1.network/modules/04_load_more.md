```
date: 2026-08-20
title: Bounded table loading for m1.network
target filename: src/m1/network/runtime.py
description: Attempts eligible table resources in table order within a selected scope and per-call limits.
```

## OWNS

- Selecting eligible table entries for `load_more()`.
- Applying the `entity`, `all`, `repeat`, `retry-rejected`, and `retry-failed`
  flags.
- Enforcing the per-invocation file-count and elapsed-time limits.
- Setting `g["load-more-complete"]` and load-more metrics for the last call.

## READS

- `table`, in its insertion order and each entity's listed-entry order.
- `resources` to learn each resource's most recent load result.
- `g` for the selected entity and loading policy limits.
- The current time for the elapsed-time limit.

## CALLS

- `import_file()` for a table entry with `type: "file"`.
- `import_url()` for a table entry with `type: "url"`.
- A small internal helper to form each entry's document key.

## MAY SAFELY ASSUME

- The import functions are atomic: an exception from either function leaves no
  data from that resource in `aspects` or `sources`.
- `table` preserves insertion order, and every table location has a supported
  `type` with the fields needed by that type.
- `g["load-more-max-files"]` is a positive integer or `None`, and
  `g["load-more-stop-after-seconds"]` is a non-negative number or `None`.

## ENSURES

- The default scope, and explicit `entity` scope, consider only locations for
  the selected entity. `all` considers every table entry, in table order.
- One invocation never attempts more than the configured file count or runs
  beyond the configured time budget, except for completing an import already
  started before the time check. A `None` value disables its corresponding
  bound without disabling the other bound.
- Failed and rejected resources contribute no entity or aspect data to the
  network; loading continues with later eligible entries.
- A `REJECTED` resource is skipped unless `retry-rejected` is supplied; a
  `FAILED` resource is skipped unless `retry-failed` is supplied.
- `repeat` discovers table locations appended by successful imports during the
  same invocation without retrying a resource already attempted in that call.
- `g["load-more-complete"]` is `True` exactly when the requested scope reaches
  a stable point with no eligible, unattempted location remaining; it is
  `False` when a configured limit ends the call first.

## DOES NOT OWN

- Parsing, validating, rejecting, or committing an individual transport
  document.
- Table construction, table merge policy, or the meaning of table locations.
- Resource serialization, saving, aspect edits, or selection changes.
- Retrying a failed or rejected resource unless the caller explicitly supplied
  its corresponding retry flag.

## PSEUDOCODE

```python
def load_more(flags=None):
    flags = flags or []
    validate_load_more_flags(flags)
    reset_last_load_more_metrics()

    attempted_document_keys = set()
    start_time = monotonic_now()
    attempted_count = 0

    while True:
        found_new_eligible_location = False

        for table_entry in iter_table_entries_in_requested_scope(flags):
            document_key = document_key_for(table_entry)
            if document_key in attempted_document_keys:
                continue
            if not is_table_entry_eligible_to_load(table_entry, flags):
                continue

            found_new_eligible_location = True
            if has_reached_load_more_limit(attempted_count, start_time):
                g["load-more-complete"] = False
                return load_more_info()

            attempted_document_keys.add(document_key)
            attempted_count += 1
            attempt_one_table_entry_and_record_metrics(table_entry)

        if "repeat" not in flags:
            g["load-more-complete"] = True
            return load_more_info()

        # Start another ordered pass. Successful imports may have appended
        # locations to `table`; attempted keys keep failures from looping.
        if not found_new_eligible_location:
            g["load-more-complete"] = True
            return load_more_info()


def iter_table_entries_in_requested_scope(flags):
    if "all" in flags:
        # Snapshot this pass.  A subsequent `repeat` pass sees table locations
        # appended by imports without mutating a collection being iterated.
        for e_id, entries in list(table.items()):
            for table_entry in list(entries):
                yield table_entry
        return

    selected_entity = require_selected_entity()
    for table_entry in list(table.get(selected_entity, [])):
        yield table_entry


def is_table_entry_eligible_to_load(table_entry, flags):
    document_key = document_key_for(table_entry)
    record = resources.get(document_key)
    if record is None:
        return True
    if record["load_result"] == "FAILED":
        return "retry-failed" in flags
    if record["load_result"] == "REJECTED":
        return "retry-rejected" in flags
    return False  # A LOADED resource is already represented in the network.


def has_reached_load_more_limit(attempted_count, start_time):
    max_files = g["load-more-max-files"]
    if max_files is not None and attempted_count >= max_files:
        return True

    max_seconds = g["load-more-stop-after-seconds"]
    if max_seconds is not None:
        return monotonic_now() - start_time >= max_seconds

    return False


def attempt_one_table_entry_and_record_metrics(table_entry):
    try:
        if table_entry["type"] == "file":
            import_file(table_entry["path"])
        else:  # table_entry["type"] == "url"
            import_url(table_entry["url"])
    except RedefinedEntityAspectError:
        g["files-rejected"] += 1
    except ResourceReadOrValidationError:
        g["files-failed"] += 1
    else:
        g["files-loaded"] += 1
```

## NOTES

- `all` and `entity` are mutually exclusive flags. Omitting both is equivalent
  to `entity`; explicitly passing `entity` is allowed for clarity.
- A previously failed or rejected entry is ignored by ordinary load passes;
  `retry-failed` and `retry-rejected` independently opt those outcomes in.
- The file-count limit counts attempted locations, not successful imports, so a
  run with inaccessible entries cannot bypass its intended bound.
- Set either policy limit to `None` to remove that limit: a `None` time limit
  still observes `load-more-max-files`, and vice versa.
- `repeat` does not relax either limit. It re-walks the live table only to find
  locations added during this call.
- Metrics should distinguish file and URL attempts if useful, but their exact
  names are presentation detail. `load-more-complete` is the authoritative
  completion signal.
