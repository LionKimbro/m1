"""The in-memory, single-owner M1 network machine."""

import json
import os
import tempfile
import uuid
from copy import deepcopy
from datetime import datetime, timezone
from pathlib import Path
from time import monotonic
from urllib.request import urlopen


BASIC_ASPECT = "tag:m1lattice.net,2026:aspect/basic"
LINK_ASPECT = "tag:m1lattice.net,2026:aspect/link"
LOG_ASPECT = "tag:m1lattice.net,2026:aspect/log"


class NetworkError(Exception):
    """Base error for the network machine."""


class UnknownEntityError(NetworkError):
    pass


class NoSelectedEntityError(NetworkError):
    pass


class UnknownAspectError(NetworkError):
    pass


class ResourceReadOrValidationError(NetworkError):
    def __init__(self, message, info=None):
        super().__init__(message)
        self.info = info or {"message": message}


class RedefinedEntityAspectError(NetworkError):
    pass


class NoTargetFileError(NetworkError):
    pass


class UnwritableResourceError(NetworkError):
    pass


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
    "last-error": None,
    "last-import-info": None,
    "files-loaded": 0,
    "files-rejected": 0,
    "urls-loaded": 0,
    "urls-rejected": 0,
    "load-more-attempted": 0,
    "load-more-files-loaded": 0,
    "load-more-files-rejected": 0,
    "load-more-files-failed": 0,
    "load-more-urls-loaded": 0,
    "load-more-urls-rejected": 0,
    "load-more-urls-failed": 0,
}


def reset_runtime():
    """Clear all network registers together."""
    aspects.clear()
    sources.clear()
    resources.clear()
    table.clear()
    dirty_filepaths.clear()
    g.clear()
    g.update({
        "selected-entity": None,
        "target-file": None,
        "load-more-max-files": 10,
        "load-more-stop-after-seconds": 1,
        "load-more-complete": None,
        "last-error": None,
        "last-import-info": None,
        "files-loaded": 0,
        "files-rejected": 0,
        "urls-loaded": 0,
        "urls-rejected": 0,
        "load-more-attempted": 0,
        "load-more-files-loaded": 0,
        "load-more-files-rejected": 0,
        "load-more-files-failed": 0,
        "load-more-urls-loaded": 0,
        "load-more-urls-rejected": 0,
        "load-more-urls-failed": 0,
    })
    return g


def canonical_path(p, flags=None):
    flags = flags or []
    candidate = Path(p)
    if "new" in flags:
        return candidate.parent.resolve(strict=True) / candidate.name
    return candidate.resolve(strict=True)


def target_file(p):
    g["target-file"] = canonical_path(p, ["new"])
    return g["target-file"]


def select_entity(e_id):
    if e_id not in aspects:
        raise UnknownEntityError(e_id)
    g["selected-entity"] = e_id
    return e_id


def known_entities():
    return list(aspects.keys())


def known_aspects():
    return list(aspects[_require_selected_entity()].keys())


def get_aspect(a_id):
    selected_entity = _require_selected_entity()
    if a_id not in aspects[selected_entity]:
        raise UnknownAspectError(selected_entity, a_id)
    return deepcopy(aspects[selected_entity][a_id])


def import_file(p):
    filepath = canonical_path(p)
    source = {"type": "file", "path": str(filepath)}
    return _load_and_commit_one_resource(source, str(filepath))


def import_url(url):
    source = {"type": "url", "url": url}
    return _load_and_commit_one_resource(source, url)


def create_entity(flags=None):
    flags = flags or []
    owner = _require_target_file_and_prepare_empty_document_if_needed()
    new_entity_id = str(uuid.uuid4())
    resources[owner]["data"]["entities"][new_entity_id] = {}
    aspects[new_entity_id] = {}
    sources[new_entity_id] = {}
    mark_file_dirty(owner)
    if "select" in flags:
        select_entity(new_entity_id)
    return new_entity_id


def set_aspect(a_id, data):
    selected_entity = _require_selected_entity()
    _require_entity_id(a_id, "aspect identifier")
    _require_json_compatible(data)
    owner = sources[selected_entity].get(a_id)
    if owner is None:
        owner = _require_target_file_and_prepare_empty_document_if_needed()
    _require_writable_file_resource(owner)
    entity = resources[owner]["data"]["entities"].setdefault(selected_entity, {})
    entity.pop("tombstone", None)
    tombstones = entity.get("tombstones")
    if tombstones is not None:
        entity["tombstones"] = [item for item in tombstones if item != a_id]
        if not entity["tombstones"]:
            entity.pop("tombstones")
    entity[a_id] = deepcopy(data)
    aspects[selected_entity][a_id] = deepcopy(data)
    sources[selected_entity][a_id] = owner
    mark_file_dirty(owner)


def delete_aspect(a_id):
    selected_entity = _require_selected_entity()
    if a_id not in aspects[selected_entity]:
        raise UnknownAspectError(selected_entity, a_id)
    owner = sources[selected_entity][a_id]
    _require_writable_file_resource(owner)
    resources[owner]["data"]["entities"][selected_entity].pop(a_id, None)
    del aspects[selected_entity][a_id]
    del sources[selected_entity][a_id]
    mark_file_dirty(owner)


def mark_file_dirty(canonical_filepath):
    filepath = str(canonical_filepath)
    resources[filepath]["dirty"] = True
    dirty_filepaths.add(filepath)


def save_file(p):
    filepath = str(canonical_path(p, ["new"]))
    record = resources.get(filepath)
    if record is None or not record["dirty"]:
        return False
    try:
        emitted_document = _make_document_for_next_emission(record["data"])
        _atomically_write_json(Path(filepath), emitted_document)
    except OSError as error:
        g["last-error"] = {"operation": "save", "path": filepath, "message": str(error)}
        raise
    record["data"] = emitted_document
    record["dirty"] = False
    dirty_filepaths.discard(filepath)
    return True


def save_files():
    return [filepath for filepath in list(dirty_filepaths) if save_file(filepath)]


def load_more(flags=None):
    flags = flags or []
    _validate_load_more_flags(flags)
    _reset_last_load_more_metrics()
    attempted_document_keys = set()
    start_time = monotonic()
    attempted_count = 0
    while True:
        found_new_eligible_location = False
        for table_entry in _iter_table_entries_in_requested_scope(flags):
            document_key = _document_key_for(table_entry)
            if document_key in attempted_document_keys:
                continue
            if not _is_table_entry_eligible_to_load(table_entry, flags):
                continue
            found_new_eligible_location = True
            if _has_reached_load_more_limit(attempted_count, start_time):
                g["load-more-complete"] = False
                return _load_more_info()
            attempted_document_keys.add(document_key)
            attempted_count += 1
            g["load-more-attempted"] += 1
            _attempt_one_table_entry_and_record_metrics(table_entry)
        if "repeat" not in flags or not found_new_eligible_location:
            g["load-more-complete"] = True
            return _load_more_info()


def _load_and_commit_one_resource(source, document_key):
    staged_record = {
        "source": deepcopy(source), "data": None, "dirty": False,
        "writable": source["type"] == "file", "load_attempted": _now(),
        "load_result": None,
    }
    try:
        staged_record["data"] = _read_and_parse_transport_document(source)
        staged_pairs = _validate_and_normalize_document(staged_record["data"])
    except ResourceReadOrValidationError as error:
        staged_record["load_result"] = "FAILED"
        staged_record["load-error-info"] = error.info
        _record_unsuccessful_load(document_key, staged_record)
        g["last-error"] = error.info
        raise
    if _any_entity_aspect_pair_is_already_loaded(staged_pairs):
        staged_record["load_result"] = "REJECTED"
        _record_unsuccessful_load(document_key, staged_record)
        _increment_import_metric(source, "rejected")
        raise RedefinedEntityAspectError(document_key)
    staged_record["load_result"] = "LOADED"
    _commit_entire_validated_document(staged_pairs, document_key, staged_record)
    _increment_import_metric(source, "loaded")
    info = {"document-key": document_key, "entity-aspects": len(staged_pairs)}
    g["last-import-info"] = info
    return info


def _read_and_parse_transport_document(source):
    try:
        if source["type"] == "file":
            text = Path(source["path"]).read_text(encoding="utf-8")
        else:
            with urlopen(source["url"]) as response:
                text = response.read().decode("utf-8")
        return json.loads(text)
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as error:
        raise ResourceReadOrValidationError(str(error), {"message": str(error)}) from error


def _validate_and_normalize_document(document):
    try:
        _require_json_compatible(document)
        if not isinstance(document, dict):
            raise ValueError("M1 transport must be a JSON object.")
        header = document.get("m1")
        if not isinstance(header, dict):
            raise ValueError("M1 transport requires an m1 header object.")
        header["id"] = _normalize_uuid(header.get("id"), "m1.id")
        if "series_id" in header:
            header["series_id"] = _normalize_uuid(header["series_id"], "m1.series_id")
        if header.get("version") != "3.0":
            raise ValueError("M1 transport version must be '3.0'.")
        _require_timestamp(header.get("timestamp"), "m1.timestamp")
        entities = document.get("entities", {})
        if not isinstance(entities, dict):
            raise ValueError("entities must be a JSON object.")
        document["entities"] = _normalize_entities(entities)
        if "table" in document and not isinstance(document["table"], dict):
            raise ValueError("table must be a JSON object.")
    except (TypeError, ValueError) as error:
        raise ResourceReadOrValidationError(str(error), {"message": str(error)}) from error
    return [
        (entity_id, aspect_id, data)
        for entity_id, entity in document["entities"].items()
        for aspect_id, data in entity.items()
        if aspect_id not in ("tombstone", "tombstones")
    ]


def _normalize_entities(entities):
    normalized = {}
    for entity_id, entity in entities.items():
        entity_id = _normalize_entity_id(entity_id, "entity identifier")
        if entity_id in normalized:
            raise ValueError("Entity identifiers collide after UUID normalization.")
        if not isinstance(entity, dict):
            raise ValueError("Each entity contribution must be a JSON object.")
        normalized[entity_id] = _normalize_entity_contribution(entity)
    return normalized


def _normalize_entity_contribution(entity):
    has_tombstone = "tombstone" in entity
    has_tombstones = "tombstones" in entity
    if has_tombstone and has_tombstones:
        raise ValueError("An entity cannot have both tombstone and tombstones.")
    if has_tombstone and entity["tombstone"] is not True:
        raise ValueError("An entity tombstone must be true.")
    normalized = {}
    for aspect_id, data in entity.items():
        if aspect_id in ("tombstone", "tombstones"):
            continue
        normalized_id = _normalize_entity_id(aspect_id, "aspect identifier")
        if normalized_id in normalized:
            raise ValueError("Aspect identifiers collide after UUID normalization.")
        normalized[normalized_id] = data
    if has_tombstone and normalized:
        raise ValueError("An entity tombstone cannot include aspects.")
    if has_tombstones:
        tombstones = entity["tombstones"]
        if not isinstance(tombstones, list):
            raise ValueError("Aspect tombstones must be an array.")
        normalized_tombstones = [_normalize_entity_id(item, "aspect tombstone") for item in tombstones]
        if set(normalized) & set(normalized_tombstones):
            raise ValueError("An aspect cannot be contributed and tombstoned together.")
        normalized["tombstones"] = normalized_tombstones
    if has_tombstone:
        normalized["tombstone"] = True
    return normalized


def _any_entity_aspect_pair_is_already_loaded(staged_pairs):
    return any(aspect_id in aspects.get(entity_id, {}) for entity_id, aspect_id, _data in staged_pairs)


def _commit_entire_validated_document(staged_pairs, document_key, staged_record):
    resources[document_key] = staged_record
    for entity_id in staged_record["data"]["entities"]:
        aspects.setdefault(entity_id, {})
        sources.setdefault(entity_id, {})
    for entity_id, aspect_id, data in staged_pairs:
        aspects[entity_id][aspect_id] = deepcopy(data)
        sources[entity_id][aspect_id] = document_key
    for entity_id, entries in staged_record["data"].get("table", {}).items():
        table.setdefault(entity_id, []).extend(deepcopy(entries))


def _require_target_file_and_prepare_empty_document_if_needed():
    target = g["target-file"]
    if target is None:
        raise NoTargetFileError("No target file selected.")
    owner = str(target)
    if owner not in resources:
        now = _now()
        resources[owner] = {
            "source": {"type": "file", "path": owner},
            "data": {"m1": {"id": str(uuid.uuid4()), "series_id": str(uuid.uuid4()), "version": "3.0", "created": now, "timestamp": now}, "entities": {}},
            "dirty": False, "writable": True, "load_attempted": None, "load_result": "NEW",
        }
    return owner


def _require_selected_entity():
    selected_entity = g["selected-entity"]
    if selected_entity is None:
        raise NoSelectedEntityError("No entity selected.")
    return selected_entity


def _require_writable_file_resource(owner):
    if not resources[owner]["writable"]:
        raise UnwritableResourceError(owner)


def _record_unsuccessful_load(document_key, staged_record):
    if resources.get(document_key, {}).get("load_result") != "LOADED":
        resources[document_key] = staged_record


def _increment_import_metric(source, outcome):
    kind = "files" if source["type"] == "file" else "urls"
    g[f"{kind}-{outcome}"] += 1


def _validate_load_more_flags(flags):
    if not isinstance(flags, list) or not all(isinstance(flag, str) for flag in flags):
        raise ValueError("load_more flags must be a list of strings.")
    allowed = {"all", "entity", "repeat", "retry-rejected", "retry-failed"}
    unknown = set(flags) - allowed
    if unknown:
        raise ValueError(f"Unknown load_more flags: {sorted(unknown)}")
    if "all" in flags and "entity" in flags:
        raise ValueError("load_more flags all and entity are mutually exclusive.")


def _reset_last_load_more_metrics():
    for kind in ("files", "urls"):
        for outcome in ("loaded", "rejected", "failed"):
            g[f"load-more-{kind}-{outcome}"] = 0
    g["load-more-attempted"] = 0
    g["load-more-complete"] = None


def _iter_table_entries_in_requested_scope(flags):
    if "all" in flags:
        for _entity_id, entries in list(table.items()):
            yield from list(entries)
        return
    selected_entity = _require_selected_entity()
    yield from list(table.get(selected_entity, []))


def _document_key_for(table_entry):
    if table_entry["type"] == "file":
        return str(canonical_path(table_entry["path"]))
    return table_entry["url"]


def _is_table_entry_eligible_to_load(table_entry, flags):
    record = resources.get(_document_key_for(table_entry))
    if record is None:
        return True
    if record["load_result"] == "FAILED":
        return "retry-failed" in flags
    if record["load_result"] == "REJECTED":
        return "retry-rejected" in flags
    return False


def _has_reached_load_more_limit(attempted_count, start_time):
    max_files = g["load-more-max-files"]
    if max_files is not None and attempted_count >= max_files:
        return True
    max_seconds = g["load-more-stop-after-seconds"]
    return max_seconds is not None and monotonic() - start_time >= max_seconds


def _attempt_one_table_entry_and_record_metrics(table_entry):
    kind = "files" if table_entry["type"] == "file" else "urls"
    try:
        if table_entry["type"] == "file":
            import_file(table_entry["path"])
        else:
            import_url(table_entry["url"])
    except RedefinedEntityAspectError:
        g[f"load-more-{kind}-rejected"] += 1
    except ResourceReadOrValidationError:
        g[f"load-more-{kind}-failed"] += 1
    else:
        g[f"load-more-{kind}-loaded"] += 1


def _load_more_info():
    return {
        "complete": g["load-more-complete"],
        "attempted": g["load-more-attempted"],
        "files": {outcome: g[f"load-more-files-{outcome}"] for outcome in ("loaded", "rejected", "failed")},
        "urls": {outcome: g[f"load-more-urls-{outcome}"] for outcome in ("loaded", "rejected", "failed")},
    }


def _normalize_uuid(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a UUID string.")
    try:
        normalized = str(uuid.UUID(value))
    except ValueError as error:
        raise ValueError(f"{label} must be a UUID string.") from error
    if value.lower() != normalized:
        raise ValueError(f"{label} must use lowercase hyphenated UUID form.")
    return normalized


def _normalize_entity_id(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be a UUID or Tag URI string.")
    if value.startswith("tag:") and len(value) > 4:
        return value
    return _normalize_uuid(value, label)


def _require_entity_id(value, label):
    _normalize_entity_id(value, label)


def _require_timestamp(value, label):
    if not isinstance(value, str):
        raise ValueError(f"{label} must be an ISO 8601 timestamp string.")
    try:
        datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as error:
        raise ValueError(f"{label} must be an ISO 8601 timestamp string.") from error


def _require_json_compatible(value):
    try:
        json.dumps(value, allow_nan=False)
    except (TypeError, ValueError) as error:
        raise ValueError("Value must be JSON-compatible.") from error


def _make_document_for_next_emission(document):
    emitted = deepcopy(document)
    header = emitted["m1"]
    header["id"] = str(uuid.uuid4())
    header.setdefault("series_id", str(uuid.uuid4()))
    header["timestamp"] = _now()
    return emitted


def _atomically_write_json(filepath, document):
    encoded = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n"
    descriptor, temporary_name = tempfile.mkstemp(prefix=f".{filepath.name}.", suffix=".tmp", dir=filepath.parent, text=True)
    try:
        with os.fdopen(descriptor, "w", encoding="utf-8", newline="\n") as output:
            output.write(encoded)
        os.replace(temporary_name, filepath)
    except BaseException:
        try:
            os.unlink(temporary_name)
        except FileNotFoundError:
            pass
        raise


def _now():
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")
