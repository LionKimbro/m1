import json
import uuid
from copy import deepcopy
from datetime import datetime
from datetime import timezone
from pathlib import Path


OVERLAY = "overlay"
ENTITY_TOMBSTONE = "tag:m1lattice.net,2026:aspect/tombstone"


def _new_state():
    return {
        "target_entity": None,
        "overlay": {},
        "overlay_headers": {},
        "overlay_table": {},
        "omit_entities": set(),
        "omit_aspects": {},
        "cache": {},
        "source": {},
        "table_cache": {},
        "M1": {},
        "M1_loaded_from": {},
        "priority": [],
        "load_order": [],
    }


g = _new_state()


def reset():
    g.clear()
    g.update(_new_state())
    return g


def claimspace():
    return g


def target_entity(entity_id):
    g["target_entity"] = entity_id


def get_entity():
    return g["target_entity"]


def clear_target():
    g["target_entity"] = None


def get_overlay():
    return {
        "m1": deepcopy(g["overlay_headers"]),
        "entities": deepcopy(g["overlay"]),
        "table": deepcopy(g["overlay_table"]),
    }


def clear_overlay():
    clear_cache()
    g["overlay"].clear()
    g["overlay_headers"].clear()
    g["overlay_table"].clear()
    clear_omissions()


def get_headers():
    return deepcopy(g["overlay_headers"])


def set_uuid(s):
    g["overlay_headers"]["id"] = s


def stamp_creation():
    g["overlay_headers"]["created"] = _now()


def set_author(s):
    g["overlay_headers"]["author"] = s


def set_title(s):
    g["overlay_headers"]["title"] = s


def set_description(s):
    g["overlay_headers"]["description"] = s


def set_hook(s):
    g["overlay_headers"]["hook"] = s


def set_headers(D):
    for k, v in D.items():
        g["overlay_headers"][k] = deepcopy(v)


def set_aspect(aspect_id, aspect_data):
    entity_id = _require_target()
    entity = g["overlay"].setdefault(entity_id, {})
    entity[aspect_id] = deepcopy(aspect_data)
    g["overlay_headers"].pop("id", None)
    _clear_cache_for_entity(entity_id)
    found, value, src = _resolve_aspect(entity_id, aspect_id)
    if found:
        g["cache"].setdefault(entity_id, {})[aspect_id] = deepcopy(value)
        g["source"].setdefault(entity_id, {})[aspect_id] = src


def tombstone_aspect(aspect_id):
    set_aspect(aspect_id, None)


def tombstone_entity(metadata=None):
    entity_id = _require_target()
    if metadata is None:
        value = {}
    elif isinstance(metadata, dict):
        value = deepcopy(metadata)
    else:
        raise TypeError("Entity tombstone metadata must be a dictionary or None.")
    value["entity"] = True
    g["overlay"][entity_id] = {ENTITY_TOMBSTONE: value}
    g["overlay_headers"].pop("id", None)
    _clear_cache_for_entity(entity_id)
    g["cache"][entity_id] = {ENTITY_TOMBSTONE: deepcopy(value)}
    g["source"][entity_id] = {ENTITY_TOMBSTONE: OVERLAY}


def has_entity_tombstone(entity_id=None):
    if entity_id is None:
        entity_id = _require_target()
    found, value, _src = _resolve_tombstone(entity_id)
    return found and _is_active_entity_tombstone(value)


def omit_aspect(aspect_id):
    entity_id = _require_target()
    g["omit_aspects"].setdefault(entity_id, set()).add(aspect_id)
    g["overlay_headers"].pop("id", None)


def omit_entity(entity_id=None):
    if entity_id is None:
        entity_id = _require_target()
    g["omit_entities"].add(entity_id)
    g["overlay_headers"].pop("id", None)


def get_omissions():
    return {
        "entities": sorted(g["omit_entities"]),
        "aspects": {
            entity_id: sorted(aspect_ids)
            for entity_id, aspect_ids in sorted(g["omit_aspects"].items())
        },
    }


def clear_omissions():
    g["omit_entities"].clear()
    g["omit_aspects"].clear()
    g["overlay_headers"].pop("id", None)


def get_aspect(aspect_id):
    entity_id = _require_target()
    if aspect_id in g["cache"].get(entity_id, {}):
        return deepcopy(g["cache"][entity_id][aspect_id])
    found, value, src = _resolve_aspect(entity_id, aspect_id)
    if not found:
        return None
    g["cache"].setdefault(entity_id, {})[aspect_id] = deepcopy(value)
    g["source"].setdefault(entity_id, {})[aspect_id] = src
    return deepcopy(value)


def has_aspect(aspect_id, flags=""):
    entity_id = _require_target()
    found, value, _src = _resolve_aspect(entity_id, aspect_id)
    if "*" in flags:
        return found
    return found and value is not None


def list_entities():
    return sorted(entity_id for entity_id in _collect_entities() if _entity_is_visible(entity_id))


def has_entity(entity_id):
    return entity_id in _collect_entities() and _entity_is_visible(entity_id)


def list_aspects(flags=""):
    entity_id = _require_target()
    aspect_ids = []
    for aspect_id in sorted(_collect_aspects(entity_id)):
        found, value, _src = _resolve_aspect(entity_id, aspect_id)
        if not found:
            continue
        if "*" in flags or value is not None:
            aspect_ids.append(aspect_id)
    return aspect_ids


def get_surface(flags=""):
    D = {}
    for aspect_id in list_aspects("*" if "*" in flags else ""):
        value = get_aspect(aspect_id)
        if value is None and "*" not in flags:
            continue
        D[aspect_id] = deepcopy(value)
    return D


def source_aspect(aspect_id):
    entity_id = _require_target()
    if aspect_id not in g["source"].get(entity_id, {}):
        if aspect_id not in _collect_aspects(entity_id):
            return None
        get_aspect(aspect_id)
    src = g["source"].get(entity_id, {}).get(aspect_id)
    if src == OVERLAY:
        return None
    return src


def loaded_from(m1_id):
    return g["M1_loaded_from"].get(m1_id)


def list_m1():
    return list(g["M1"].keys())


def get_m1(m1_id):
    return deepcopy(g["M1"][m1_id])


def has_m1(m1_id):
    return m1_id in g["M1"]


def list_priority():
    return list(g["priority"])


def order(kind, flags=""):
    reverse = "-" in flags
    if kind == "ts":
        g["priority"] = sorted(g["priority"], key=_timestamp_for_m1, reverse=reverse)
    elif kind == "load-order":
        order_map = {m1_id: i for i, m1_id in enumerate(g["load_order"])}
        g["priority"] = sorted(g["priority"], key=lambda m1_id: order_map.get(m1_id, 10**9), reverse=reverse)
    elif isinstance(kind, list):
        g["priority"] = list(kind)
        if reverse:
            g["priority"].reverse()
    else:
        raise ValueError(kind)
    clear_cache()


def clear_cache(which=None):
    if which is None:
        g["cache"].clear()
        g["source"].clear()
        g["table_cache"].clear()
        return
    if which == OVERLAY:
        _clear_cache_for_entities(g["overlay"])
        for key in g["overlay_table"]:
            g["table_cache"].pop(key, None)
        return
    if which not in g["M1"]:
        return
    D = g["M1"][which]
    _clear_cache_for_entities(D.get("entities", {}))
    for key in D.get("table", {}):
        g["table_cache"].pop(key, None)


def refresh():
    clear_cache()
    for entity_id in _collect_entities():
        for aspect_id in _collect_aspects(entity_id):
            get_aspect_for(entity_id, aspect_id)
    for key in _collect_table_ids():
        resolve_table(key)


def drop_m1(which):
    if which == "all":
        g["M1"].clear()
        g["M1_loaded_from"].clear()
        g["priority"].clear()
        g["load_order"].clear()
        clear_cache()
        return
    if which not in g["M1"]:
        return
    clear_cache(which)
    g["M1"].pop(which, None)
    g["M1_loaded_from"].pop(which, None)
    g["priority"] = [m1_id for m1_id in g["priority"] if m1_id != which]
    g["load_order"] = [m1_id for m1_id in g["load_order"] if m1_id != which]


def weed_table():
    for key in list(g["overlay_table"].keys()):
        L = []
        for item in g["overlay_table"][key]:
            if item.get("type") == "file":
                path = item.get("path")
                if path and Path(path).exists():
                    L.append(item)
            else:
                L.append(item)
        if L:
            g["overlay_table"][key] = L
        else:
            del g["overlay_table"][key]
        g["table_cache"].pop(key, None)


def load_m1(path, flags=""):
    p = Path(path).resolve()
    D = json.loads(p.read_text(encoding="utf-8"))
    return load_transport(D, path=p, flags=flags)


def load_files(paths):
    for path in paths:
        load_m1(path)
    return g


def load_transport(D, path=None, flags=""):
    validate_transport(D)
    include_table = "t" in flags
    keep = "k" in flags
    mode = _load_mode(flags)
    action = _action(flags, default="+")
    path_str = str(Path(path).resolve()) if path is not None else None
    if "w" in flags and not include_table:
        raise ValueError("w requires t.")
    if action == "-" and mode == "S" and g["M1"]:
        raise ValueError("Refusing S- load because M1 data is already loaded.")
    if action == "-" and mode == "O" and g["overlay"]:
        raise ValueError("Refusing O- load because overlay is not empty.")
    if action == "-" and mode == "" and _priority_load_conflict(D, path_str):
        raise ValueError("Refusing safe load of already loaded M1.")
    if path_str and not keep:
        _drop_loaded_from_path(path_str)
    if mode == "O":
        _load_into_overlay(D, include_table, action)
    elif mode == "S":
        _load_snapshot(D, include_table, action, keep, path_str)
    else:
        _load_into_priority(D, include_table, action, path_str)
    if include_table:
        _invalidate_table_from_doc(D)
    if "w" in flags:
        weed_table()
    return g


def save_m1(path, flags=""):
    p = Path(path)
    include_table = "t" in flags
    if "w" in flags:
        if not include_table:
            raise ValueError("w requires t.")
        weed_table()
    mode = _save_mode(flags)
    action = _action(flags, default="!")
    if action == "-" and p.exists():
        raise FileExistsError(str(p))
    if action == "+" and p.exists():
        base = json.loads(p.read_text(encoding="utf-8"))
    else:
        base = None
    if mode == "S":
        D = _build_snapshot_doc(base, include_table)
    else:
        D = _build_overlay_doc(base, include_table)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(D, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return D


def validate_transport(D):
    if not isinstance(D, dict):
        raise TypeError("M1 transport must be a dictionary.")
    if "m1" not in D or not isinstance(D["m1"], dict):
        raise ValueError("M1 transport is missing the m1 header.")
    if "id" not in D["m1"] or "timestamp" not in D["m1"]:
        raise ValueError("M1 transport requires m1.id and m1.timestamp.")
    if "entities" in D and not isinstance(D["entities"], dict):
        raise TypeError("entities must be a dictionary.")
    if "table" in D and not isinstance(D["table"], dict):
        raise TypeError("table must be a dictionary.")


def resolve_table(identifier):
    if identifier in g["table_cache"]:
        return deepcopy(g["table_cache"][identifier])
    found, value = _resolve_table(identifier)
    if not found:
        return []
    g["table_cache"][identifier] = deepcopy(value)
    return deepcopy(value)


def load_file(path):
    return load_m1(path)


def all_entities():
    return list_entities()


def all_aspects(entity_id):
    old = g["target_entity"]
    g["target_entity"] = entity_id
    try:
        return list_aspects("*")
    finally:
        g["target_entity"] = old


def get_latest_aspect(entity_id, aspect_id):
    found, value, src = _resolve_aspect(entity_id, aspect_id)
    if not found:
        return None
    return {
        "entity_id": entity_id,
        "aspect_id": aspect_id,
        "aspect": deepcopy(value),
        "source_hash": src,
    }


def get_claims(entity_id, aspect_id):
    claim = get_latest_aspect(entity_id, aspect_id)
    if claim is None:
        return []
    return [claim]


def get_entity_sources(entity_id):
    L = []
    if entity_id in g["overlay"]:
        L.append(OVERLAY)
    for m1_id, D in g["M1"].items():
        if entity_id in D.get("entities", {}):
            L.append(m1_id)
    return L


def get_source(source_id):
    if source_id == OVERLAY:
        return {
            "paths": [],
            "title": "Overlay",
            "timestamp": None,
            "created": g["overlay_headers"].get("created"),
        }
    if source_id not in g["M1"]:
        return None
    header = g["M1"][source_id]["m1"]
    path = g["M1_loaded_from"].get(source_id)
    paths = [] if path is None else [path]
    return {
        "paths": paths,
        "title": header.get("title"),
        "timestamp": header.get("timestamp"),
        "created": header.get("created"),
    }


def get_aspect_for(entity_id, aspect_id):
    old = g["target_entity"]
    g["target_entity"] = entity_id
    try:
        return get_aspect(aspect_id)
    finally:
        g["target_entity"] = old


def _build_overlay_doc(base, include_table):
    if base is not None:
        entities = _merge_entities(base.get("entities", {}), g["overlay"])
        table = _merge_table(base.get("table", {}), g["overlay_table"]) if include_table else None
    else:
        entities = deepcopy(g["overlay"])
        table = deepcopy(g["overlay_table"]) if include_table else None
    entities = _apply_omissions(entities)
    if table is not None:
        table = _apply_table_omissions(table)
    return _emit_doc(entities, table, base)


def _build_snapshot_doc(base, include_table):
    entities = {}
    for entity_id in sorted(_collect_entities()):
        old = g["target_entity"]
        g["target_entity"] = entity_id
        try:
            visible_entity = _entity_is_visible(entity_id)
            if visible_entity:
                aspect_ids = [
                    aspect_id
                    for aspect_id in list_aspects("*")
                    if aspect_id != ENTITY_TOMBSTONE
                ]
            elif has_entity_tombstone(entity_id):
                aspect_ids = [ENTITY_TOMBSTONE]
            else:
                aspect_ids = []
            if not aspect_ids:
                continue
            entities[entity_id] = {}
            for aspect_id in aspect_ids:
                entities[entity_id][aspect_id] = get_aspect(aspect_id)
        finally:
            g["target_entity"] = old
    if base is not None:
        entities = _merge_entities(base.get("entities", {}), entities)
    entities = _apply_omissions(entities)
    if include_table:
        table = {}
        for key in sorted(_collect_table_ids()):
            table[key] = resolve_table(key)
        if base is not None:
            table = _merge_table(base.get("table", {}), table)
        table = _apply_table_omissions(table)
    else:
        table = None
    return _emit_doc(entities, table, base)


def _emit_doc(entities, table, base):
    header = {}
    if base is not None and "m1" in base:
        for k, v in base["m1"].items():
            if k not in ("id", "timestamp"):
                header[k] = deepcopy(v)
    for k, v in g["overlay_headers"].items():
        if k not in ("timestamp",):
            header[k] = deepcopy(v)
    header["id"] = header.get("id") or str(uuid.uuid4())
    header["timestamp"] = _now()
    if "version" not in header:
        header["version"] = "2.0"
    D = {
        "m1": header,
        "entities": entities,
    }
    if table is not None:
        D["table"] = table
    return D


def _load_into_overlay(D, include_table, action):
    if action == "!":
        clear_cache()
        g["overlay"].clear()
        g["overlay_headers"].clear()
        g["overlay_table"].clear()
        clear_omissions()
    elif action == "-":
        if g["overlay"]:
            raise ValueError("Overlay is not empty.")
    for entity_id, aspects in D.get("entities", {}).items():
        entity = g["overlay"].setdefault(entity_id, {})
        for aspect_id, value in aspects.items():
            entity[aspect_id] = deepcopy(value)
        _clear_cache_for_entity(entity_id)
    if include_table:
        for key, L in D.get("table", {}).items():
            g["overlay_table"][key] = deepcopy(L)
    for k, v in D.get("m1", {}).items():
        if k not in ("id", "timestamp", "version"):
            g["overlay_headers"][k] = deepcopy(v)


def _load_into_priority(D, include_table, action, path_str):
    m1_id = D["m1"]["id"]
    if action == "-" and _priority_load_conflict(D, path_str):
        raise ValueError("Refusing safe load of already loaded M1.")
    doc = _copy_doc_for_runtime(D, include_table)
    g["M1"][m1_id] = doc
    if path_str is not None:
        g["M1_loaded_from"][m1_id] = path_str
    if m1_id not in g["load_order"]:
        g["load_order"].append(m1_id)
    g["priority"] = [x for x in g["priority"] if x != m1_id]
    g["priority"].insert(0, m1_id)
    clear_cache(m1_id)


def _load_snapshot(D, include_table, action, keep, path_str):
    if action == "!":
        g["M1"].clear()
        g["M1_loaded_from"].clear()
        g["priority"].clear()
        g["load_order"].clear()
        clear_cache()
        if not keep:
            g["overlay"].clear()
            g["overlay_headers"].clear()
            g["overlay_table"].clear()
            clear_omissions()
        _load_into_priority(D, include_table, "+", path_str)
    elif action == "+":
        _load_into_priority(D, include_table, "+", path_str)
        m1_id = D["m1"]["id"]
        g["priority"] = [x for x in g["priority"] if x != m1_id]
        g["priority"].insert(0, m1_id)
        clear_cache()
    elif action == "-":
        if g["M1"]:
            raise ValueError("Refusing S- load because M1 data is already loaded.")
        _load_into_priority(D, include_table, "+", path_str)
    else:
        raise ValueError(action)


def _copy_doc_for_runtime(D, include_table):
    doc = {
        "m1": deepcopy(D["m1"]),
        "entities": deepcopy(D.get("entities", {})),
    }
    if include_table and "table" in D:
        doc["table"] = deepcopy(D["table"])
    return doc


def _drop_loaded_from_path(path_str):
    L = [m1_id for m1_id, loaded_path in g["M1_loaded_from"].items() if loaded_path == path_str]
    for m1_id in L:
        drop_m1(m1_id)


def _require_target():
    entity_id = g["target_entity"]
    if entity_id is None:
        raise ValueError("No target entity set.")
    return entity_id


def _resolve_aspect(entity_id, aspect_id):
    layers = _layers()
    if aspect_id == ENTITY_TOMBSTONE:
        return _resolve_aspect_in_layers(entity_id, aspect_id, layers)
    tombstone_found, tombstone_value, tombstone_source = _resolve_tombstone(entity_id)
    if tombstone_found and _is_active_entity_tombstone(tombstone_value):
        cutoff = _layer_index(tombstone_source)
        layers = layers[:cutoff]
    return _resolve_aspect_in_layers(entity_id, aspect_id, layers)


def _resolve_aspect_in_layers(entity_id, aspect_id, layers):
    for source_id, aspects in layers:
        aspects = aspects.get(entity_id, {})
        if aspect_id in aspects:
            return True, deepcopy(aspects[aspect_id]), source_id
    return False, None, None


def _resolve_tombstone(entity_id):
    return _resolve_aspect_in_layers(entity_id, ENTITY_TOMBSTONE, _layers())


def _layers():
    layers = [(OVERLAY, g["overlay"])]
    for m1_id in g["priority"]:
        layers.append((m1_id, g["M1"].get(m1_id, {}).get("entities", {})))
    return layers


def _layer_index(source_id):
    if source_id == OVERLAY:
        return 0
    return 1 + g["priority"].index(source_id)


def _entity_is_visible(entity_id):
    tombstone_found, tombstone_value, tombstone_source = _resolve_tombstone(entity_id)
    if not tombstone_found or not _is_active_entity_tombstone(tombstone_value):
        return entity_id in _collect_entities()
    cutoff = _layer_index(tombstone_source)
    for _source_id, entities in _layers()[:cutoff]:
        if entity_id in entities:
            return True
    return False


def _is_active_entity_tombstone(value):
    return isinstance(value, dict) and value.get("entity") is True


def _resolve_table(identifier):
    if identifier in g["overlay_table"]:
        return True, deepcopy(g["overlay_table"][identifier])
    for m1_id in g["priority"]:
        table = g["M1"].get(m1_id, {}).get("table", {})
        if identifier in table:
            return True, deepcopy(table[identifier])
    return False, []


def _collect_entities():
    s = set(g["overlay"].keys())
    for D in g["M1"].values():
        s.update(D.get("entities", {}).keys())
    return s


def _collect_aspects(entity_id):
    s = set(g["overlay"].get(entity_id, {}).keys())
    for D in g["M1"].values():
        s.update(D.get("entities", {}).get(entity_id, {}).keys())
    return s


def _collect_table_ids():
    s = set(g["overlay_table"].keys())
    for D in g["M1"].values():
        s.update(D.get("table", {}).keys())
    return s


def _clear_cache_for_entities(entities):
    for entity_id, aspects in entities.items():
        if ENTITY_TOMBSTONE in aspects:
            _clear_cache_for_entity(entity_id)
            continue
        if entity_id not in g["cache"]:
            continue
        for aspect_id in aspects:
            g["cache"][entity_id].pop(aspect_id, None)
            if entity_id in g["source"]:
                g["source"][entity_id].pop(aspect_id, None)
        if not g["cache"][entity_id]:
            g["cache"].pop(entity_id, None)
        if entity_id in g["source"] and not g["source"][entity_id]:
            g["source"].pop(entity_id, None)


def _clear_cache_for_entity(entity_id):
    g["cache"].pop(entity_id, None)
    g["source"].pop(entity_id, None)


def _merge_entities(base_entities, overlay_entities):
    D = deepcopy(base_entities)
    for entity_id, aspects in overlay_entities.items():
        if _is_active_entity_tombstone(aspects.get(ENTITY_TOMBSTONE)):
            D[entity_id] = deepcopy(aspects)
            continue
        ordinary_aspects = [aspect_id for aspect_id in aspects if aspect_id != ENTITY_TOMBSTONE]
        if ordinary_aspects and _is_active_entity_tombstone(
            D.get(entity_id, {}).get(ENTITY_TOMBSTONE)
        ):
            D[entity_id] = {}
        entity = D.setdefault(entity_id, {})
        for aspect_id, value in aspects.items():
            entity[aspect_id] = deepcopy(value)
        if not entity:
            D.pop(entity_id, None)
    return D


def _apply_omissions(entities):
    D = _normalize_entity_tombstones(entities)
    for entity_id in g["omit_entities"]:
        D.pop(entity_id, None)
    for entity_id, aspect_ids in g["omit_aspects"].items():
        if entity_id not in D:
            continue
        for aspect_id in aspect_ids:
            D[entity_id].pop(aspect_id, None)
        if not D[entity_id]:
            D.pop(entity_id, None)
    return D


def _normalize_entity_tombstones(entities):
    D = deepcopy(entities)
    for entity_id, aspects in D.items():
        tombstone = aspects.get(ENTITY_TOMBSTONE)
        if _is_active_entity_tombstone(tombstone):
            D[entity_id] = {ENTITY_TOMBSTONE: deepcopy(tombstone)}
    return D


def _apply_table_omissions(table):
    D = deepcopy(table)
    for entity_id in g["omit_entities"]:
        D.pop(entity_id, None)
    return D


def _priority_load_conflict(D, path_str):
    m1_id = D["m1"]["id"]
    if m1_id in g["M1"]:
        return True
    if path_str is None:
        return False
    return path_str in g["M1_loaded_from"].values()


def _merge_table(base_table, overlay_table):
    D = deepcopy(base_table)
    for key, value in overlay_table.items():
        D[key] = deepcopy(value)
    return D


def _timestamp_for_m1(m1_id):
    return g["M1"].get(m1_id, {}).get("m1", {}).get("timestamp", "")


def _invalidate_table_from_doc(D):
    for key in D.get("table", {}):
        g["table_cache"].pop(key, None)


def _load_mode(flags):
    if "S" in flags:
        return "S"
    if "O" in flags:
        return "O"
    return ""


def _save_mode(flags):
    if "S" in flags:
        return "S"
    return "O"


def _action(flags, default):
    L = [ch for ch in "+!-" if ch in flags]
    if len(L) > 1:
        raise ValueError("Conflicting action flags.")
    if L:
        return L[0]
    return default


def _now():
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z")
