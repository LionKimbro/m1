import json
import hashlib
from copy import deepcopy
from pathlib import Path


def _new_claimspace():
    return {
        "claims": {},
        "entity_sources": {},
        "sources": {},
        "seq": 0,
    }


g = _new_claimspace()


def reset():
    g.clear()
    g.update(_new_claimspace())
    return g


def claimspace():
    return g


def load_file(path):
    p = Path(path)
    b = p.read_bytes()
    D = json.loads(b.decode("utf-8"))
    return load_transport(D, path=p, raw_bytes=b)


def load_files(paths):
    for path in paths:
        load_file(path)
    return g


def load_transport(D, path=None, raw_bytes=None):
    validate_transport(D)
    src = _make_source_record(D, path, raw_bytes)
    if src["hash"] in g["sources"]:
        _merge_source_path(src["hash"], src["paths"])
        return g
    g["sources"][src["hash"]] = src
    entities = D.get("entities", {})
    for entity_id, aspects in entities.items():
        _register_entity_source(entity_id, src["hash"])
        for aspect_id, aspect in aspects.items():
            add_claim(entity_id, aspect_id, aspect, src)
    return g


def validate_transport(D):
    if not isinstance(D, dict):
        raise TypeError("M1 transport must be a dictionary.")
    if "m1" not in D:
        raise ValueError("M1 transport is missing the 'm1' header.")
    if not isinstance(D["m1"], dict):
        raise TypeError("The 'm1' header must be a dictionary.")
    if "entities" in D and not isinstance(D["entities"], dict):
        raise TypeError("The 'entities' section must be a dictionary.")


def add_claim(entity_id, aspect_id, aspect, src=None):
    entity_claims = g["claims"].setdefault(entity_id, {})
    aspect_claims = entity_claims.setdefault(aspect_id, [])
    g["seq"] += 1
    claim = {
        "entity_id": entity_id,
        "aspect_id": aspect_id,
        "aspect": deepcopy(aspect),
        "seq": g["seq"],
    }
    if src is not None:
        claim["source_hash"] = src["hash"]
        _register_entity_source(entity_id, src["hash"])
    aspect_claims.append(claim)
    return claim


def has_entity(entity_id):
    return entity_id in g["claims"]


def all_aspects(entity_id):
    if entity_id not in g["claims"]:
        return []
    return list(g["claims"][entity_id].keys())


def get_claims(entity_id, aspect_id):
    if entity_id not in g["claims"]:
        return []
    if aspect_id not in g["claims"][entity_id]:
        return []
    return deepcopy(g["claims"][entity_id][aspect_id])


def get_latest_aspect(entity_id, aspect_id):
    claims = get_claims(entity_id, aspect_id)
    if not claims:
        return None
    return max(claims, key=_claim_sort_key)


def get_entity_sources(entity_id):
    if entity_id not in g["entity_sources"]:
        return []
    return list(g["entity_sources"][entity_id])


def all_entities():
    return list(g["claims"].keys())


def get_source(source_hash):
    if source_hash not in g["sources"]:
        return None
    return deepcopy(g["sources"][source_hash])


def _make_source_record(D, path, raw_bytes=None):
    p = Path(path).resolve() if path is not None else None
    header = deepcopy(D.get("m1", {}))
    if raw_bytes is None:
        raw_bytes = json.dumps(D, sort_keys=True, separators=(",", ":")).encode("utf-8")
    file_hash = hashlib.sha256(raw_bytes).hexdigest()
    paths = []
    if p is not None:
        paths.append(str(p))
    return {
        "hash": file_hash,
        "paths": paths,
        "created": header.get("created"),
        "author": header.get("author"),
        "title": header.get("title"),
        "description": header.get("description"),
        "hook": header.get("hook"),
        "version": header.get("version"),
    }


def _register_entity_source(entity_id, source_hash):
    L = g["entity_sources"].setdefault(entity_id, [])
    if source_hash not in L:
        L.append(source_hash)


def _merge_source_path(source_hash, paths):
    src = g["sources"][source_hash]
    for path in paths:
        if path not in src["paths"]:
            src["paths"].append(path)


def _claim_sort_key(claim):
    src = g["sources"].get(claim.get("source_hash"), {})
    created = src.get("created")
    if created is None:
        created = ""
    return (created, claim.get("seq", 0))
