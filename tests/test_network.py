import json
import uuid

import pytest

import m1.network as network


def _document(entity_id, aspect_id, value, series_id=None):
    header = {
        "id": "11111111-1111-4111-8111-111111111111",
        "version": "3.0",
        "timestamp": "2026-08-20T12:00:00Z",
    }
    if series_id is not None:
        header["series_id"] = series_id
    return {"m1": header, "entities": {entity_id: {aspect_id: value}}}


def test_import_is_atomic_and_rejects_existing_entity_aspect(tmp_path):
    network.reset_runtime()
    first = tmp_path / "first.m1"
    second = tmp_path / "second.m1"
    entity_id = "22222222-2222-4222-8222-222222222222"
    first.write_text(json.dumps(_document(entity_id, "tag:example:aspect/a", {"value": 1})), encoding="utf-8")
    second.write_text(json.dumps(_document(entity_id, "tag:example:aspect/a", {"value": 2})), encoding="utf-8")

    network.import_file(first)
    with pytest.raises(network.RedefinedEntityAspectError):
        network.import_file(second)

    assert network.get_aspect is not None
    network.select_entity(entity_id)
    assert network.get_aspect("tag:example:aspect/a") == {"value": 1}
    assert str(second.resolve()) in network.resources
    assert network.resources[str(second.resolve())]["load_result"] == "REJECTED"


def test_save_reemits_id_and_preserves_existing_series_id(tmp_path):
    network.reset_runtime()
    filepath = tmp_path / "working.m1"
    entity_id = "33333333-3333-4333-8333-333333333333"
    series_id = "44444444-4444-4444-8444-444444444444"
    filepath.write_text(json.dumps(_document(entity_id, "tag:example:aspect/a", {"value": 1}, series_id)), encoding="utf-8")

    network.import_file(filepath)
    original_id = network.resources[str(filepath.resolve())]["data"]["m1"]["id"]
    network.select_entity(entity_id)
    network.set_aspect("tag:example:aspect/a", {"value": 2})

    assert network.save_file(filepath)
    saved = json.loads(filepath.read_text(encoding="utf-8"))
    assert saved["m1"]["id"] != original_id
    assert saved["m1"]["series_id"] == series_id
    assert saved["entities"][entity_id]["tag:example:aspect/a"] == {"value": 2}


def test_new_target_document_gets_series_id_and_reemits_id(tmp_path):
    network.reset_runtime()
    filepath = tmp_path / "new.m1"
    network.target_file(filepath)
    entity_id = network.create_entity(["select"])
    network.set_aspect("tag:example:aspect/a", None)
    before_save = network.resources[str(filepath.resolve())]["data"]["m1"]

    assert network.save_file(filepath)
    saved = json.loads(filepath.read_text(encoding="utf-8"))
    assert saved["m1"]["id"] != before_save["id"]
    assert uuid.UUID(saved["m1"]["series_id"])
    assert saved["entities"][entity_id]["tag:example:aspect/a"] is None


def test_load_more_obeys_limits_and_repeat_discovers_imported_table_entries(tmp_path):
    network.reset_runtime()
    root = tmp_path / "root.m1"
    child = tmp_path / "child.m1"
    grandchild = tmp_path / "grandchild.m1"
    root_entity = "55555555-5555-4555-8555-555555555555"
    child_entity = "66666666-6666-4666-8666-666666666666"
    grandchild_entity = "77777777-7777-4777-8777-777777777777"
    root_data = _document(root_entity, "tag:example:aspect/a", {"value": "root"})
    root_data["table"] = {root_entity: [{"type": "file", "path": str(child)}]}
    child_data = _document(child_entity, "tag:example:aspect/a", {"value": "child"})
    child_data["table"] = {child_entity: [{"type": "file", "path": str(grandchild)}]}
    grandchild_data = _document(grandchild_entity, "tag:example:aspect/a", {"value": "grandchild"})
    root.write_text(json.dumps(root_data), encoding="utf-8")
    child.write_text(json.dumps(child_data), encoding="utf-8")
    grandchild.write_text(json.dumps(grandchild_data), encoding="utf-8")

    network.import_file(root)
    network.select_entity(root_entity)
    network.g["load-more-max-files"] = 1
    first = network.load_more()

    assert first["attempted"] == 1
    assert first["complete"] is True
    assert child_entity in network.known_entities()
    assert grandchild_entity not in network.known_entities()

    network.g["load-more-max-files"] = None
    repeated = network.load_more(["all", "repeat"])

    assert repeated["complete"] is True
    assert repeated["files"]["loaded"] == 1
    assert grandchild_entity in network.known_entities()
