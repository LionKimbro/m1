import json

import m1


def test_load_m1_and_targeted_access(tmp_path):
    m1.reset()
    p = tmp_path / "a.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "11111111-1111-4111-8111-111111111111",
                    "version": "2.0",
                    "timestamp": "2026-05-07T10:00:00Z",
                    "title": "A",
                },
                "entities": {
                    "uuid-1": {
                        "tag:m1lattice.net,2026/aspect/basic": {
                            "title": "Alpha",
                        },
                        "tag:m1lattice.net,2026/aspect/log": {
                            "log": [],
                        },
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.load_m1(p)

    assert m1.list_m1() == ["11111111-1111-4111-8111-111111111111"]
    assert m1.loaded_from("11111111-1111-4111-8111-111111111111") == str(p.resolve())
    assert m1.has_entity("uuid-1")

    m1.target_entity("uuid-1")
    assert m1.list_aspects() == [
        "tag:m1lattice.net,2026/aspect/basic",
        "tag:m1lattice.net,2026/aspect/log",
    ]
    assert m1.get_aspect("tag:m1lattice.net,2026/aspect/basic")["title"] == "Alpha"
    assert m1.source_aspect("tag:m1lattice.net,2026/aspect/basic") == "11111111-1111-4111-8111-111111111111"


def test_overlay_writes_immediately_update_selected_value():
    m1.reset()
    m1.target_entity("uuid-1")
    m1.set_aspect("tag:m1lattice.net,2026/aspect/basic", {"title": "Overlay Title"})

    assert m1.get_aspect("tag:m1lattice.net,2026/aspect/basic")["title"] == "Overlay Title"
    assert m1.source_aspect("tag:m1lattice.net,2026/aspect/basic") is None


def test_none_tombstone_covers_lower_priority(tmp_path):
    m1.reset()
    p1 = tmp_path / "one.m1"
    p2 = tmp_path / "two.m1"
    p1.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "22222222-2222-4222-8222-222222222222",
                    "version": "2.0",
                    "timestamp": "2026-05-07T10:00:00Z",
                },
                "entities": {
                    "uuid-1": {
                        "a": {"title": "One"}
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    p2.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "33333333-3333-4333-8333-333333333333",
                    "version": "2.0",
                    "timestamp": "2026-05-07T11:00:00Z",
                },
                "entities": {
                    "uuid-1": {
                        "a": None
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.load_m1(p1)
    m1.load_m1(p2)
    m1.target_entity("uuid-1")

    assert m1.get_aspect("a") is None
    assert m1.has_aspect("a", "*")
    assert not m1.has_aspect("a")


def test_reload_same_path_replaces_old_document_without_k(tmp_path):
    m1.reset()
    p = tmp_path / "same.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "44444444-4444-4444-8444-444444444444",
                    "version": "2.0",
                    "timestamp": "2026-05-07T10:00:00Z",
                },
                "entities": {"uuid-1": {"a": {"title": "One"}}},
            }
        ),
        encoding="utf-8",
    )
    m1.load_m1(p)
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "55555555-5555-4555-8555-555555555555",
                    "version": "2.0",
                    "timestamp": "2026-05-07T11:00:00Z",
                },
                "entities": {"uuid-1": {"a": {"title": "Two"}}},
            }
        ),
        encoding="utf-8",
    )
    m1.load_m1(p)

    assert not m1.has_m1("44444444-4444-4444-8444-444444444444")
    assert m1.has_m1("55555555-5555-4555-8555-555555555555")
    assert m1.loaded_from("55555555-5555-4555-8555-555555555555") == str(p.resolve())


def test_safe_reload_same_path_refuses_to_replace_existing_document(tmp_path):
    m1.reset()
    p = tmp_path / "same.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "45454545-4545-4454-8454-454545454545",
                    "version": "2.0",
                    "timestamp": "2026-05-07T10:00:00Z",
                },
                "entities": {"uuid-1": {"a": {"title": "One"}}},
            }
        ),
        encoding="utf-8",
    )
    m1.load_m1(p)
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "56565656-5656-4565-8565-565656565656",
                    "version": "2.0",
                    "timestamp": "2026-05-07T11:00:00Z",
                },
                "entities": {"uuid-1": {"a": {"title": "Two"}}},
            }
        ),
        encoding="utf-8",
    )

    try:
        m1.load_m1(p, "-")
        assert False, "Expected safe load to refuse replacing an existing same-path document."
    except ValueError:
        pass

    assert m1.has_m1("45454545-4545-4454-8454-454545454545")
    assert not m1.has_m1("56565656-5656-4565-8565-565656565656")


def test_save_amend_preserves_unspecified_headers_and_refreshes_id_and_timestamp(tmp_path):
    m1.reset()
    p = tmp_path / "out.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "66666666-6666-4666-8666-666666666666",
                    "version": "2.0",
                    "timestamp": "2026-05-07T10:00:00Z",
                    "series_id": "77777777-7777-4777-8777-777777777777",
                    "author": "Lion",
                    "title": "Existing",
                },
                "entities": {
                    "uuid-1": {
                        "a": {"title": "One"}
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.target_entity("uuid-1")
    m1.set_title("New Title")
    m1.set_aspect("b", {"title": "Two"})
    D = m1.save_m1(p, "+")

    assert D["m1"]["title"] == "New Title"
    assert D["m1"]["author"] == "Lion"
    assert D["m1"]["series_id"] == "77777777-7777-4777-8777-777777777777"
    assert D["m1"]["id"] != "66666666-6666-4666-8666-666666666666"
    assert D["m1"]["timestamp"] != "2026-05-07T10:00:00Z"


def test_snapshot_amend_preserves_visible_none_tombstones(tmp_path):
    m1.reset()
    p = tmp_path / "snapshot-out.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "67676767-6767-4676-8676-676767676767",
                    "version": "2.0",
                    "timestamp": "2026-05-07T10:00:00Z",
                },
                "entities": {
                    "uuid-1": {
                        "a": {"title": "One"}
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.load_m1(p)
    m1.target_entity("uuid-1")
    m1.set_aspect("a", None)
    D = m1.save_m1(p, "S+")

    assert "uuid-1" in D["entities"]
    assert "a" in D["entities"]["uuid-1"]
    assert D["entities"]["uuid-1"]["a"] is None


def test_table_load_requires_t_and_weed_table_removes_missing_files(tmp_path):
    m1.reset()
    missing = tmp_path / "missing.txt"
    p = tmp_path / "table.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "88888888-8888-4888-8888-888888888888",
                    "version": "2.0",
                    "timestamp": "2026-05-07T10:00:00Z",
                },
                "entities": {},
                "table": {
                    "uuid-1": [
                        {"type": "file", "path": str(missing)}
                    ]
                },
            }
        ),
        encoding="utf-8",
    )

    m1.load_m1(p)
    assert m1.resolve_table("uuid-1") == []
    m1.load_m1(p, "t")
    assert m1.resolve_table("uuid-1") == [{"type": "file", "path": str(missing)}]
    m1.load_transport(
        {
            "m1": {
                "id": "99999999-9999-4999-8999-999999999999",
                "version": "2.0",
                "timestamp": "2026-05-07T11:00:00Z",
            },
            "entities": {},
            "table": {},
        },
        flags="Ot",
    )
    m1.claimspace()["overlay_table"]["uuid-1"] = [{"type": "file", "path": str(missing)}]
    m1.weed_table()
    assert "uuid-1" not in m1.claimspace()["overlay_table"]
