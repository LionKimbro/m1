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


def test_overlay_amend_preserves_none_as_serialized_aspect_tombstone(tmp_path):
    m1.reset()
    p = tmp_path / "overlay-out.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "65656565-6565-4656-8656-656565656565",
                    "version": "2.0",
                    "timestamp": "2026-05-07T10:00:00Z",
                },
                "entities": {
                    "uuid-1": {
                        "a": {"title": "One"},
                        "b": {"title": "Two"},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.target_entity("uuid-1")
    m1.tombstone_aspect("a")
    D = m1.save_m1(p, "O+")

    assert D["entities"]["uuid-1"] == {
        "a": None,
        "b": {"title": "Two"},
    }


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


def test_entity_tombstone_covers_all_lower_aspects_and_snapshots_cleanly(tmp_path):
    m1.reset()
    m1.load_transport(
        {
            "m1": {
                "id": "aaaaaaaa-aaaa-4aaa-8aaa-aaaaaaaaaaaa",
                "version": "2.0",
                "timestamp": "2026-06-18T10:00:00Z",
            },
            "entities": {
                "uuid-1": {
                    "a": {"title": "Lower"},
                    "unknown-lower-aspect": {"value": 1},
                }
            },
        }
    )

    m1.target_entity("uuid-1")
    m1.tombstone_entity({"reason": "Hidden here"})

    assert not m1.has_entity("uuid-1")
    assert "uuid-1" not in m1.list_entities()
    assert m1.has_entity_tombstone()
    assert m1.get_aspect("a") is None
    assert not m1.has_aspect("a", "*")
    assert m1.list_aspects("*") == [m1.ENTITY_TOMBSTONE]

    D = m1.save_m1(tmp_path / "snapshot.m1", "S!")
    assert D["entities"] == {
        "uuid-1": {
            m1.ENTITY_TOMBSTONE: {
                "entity": True,
                "reason": "Hidden here",
            }
        }
    }


def test_higher_layer_can_reintroduce_tombstoned_entity(tmp_path):
    m1.reset()
    m1.load_transport(
        {
            "m1": {
                "id": "bbbbbbbb-bbbb-4bbb-8bbb-bbbbbbbbbbbb",
                "version": "2.0",
                "timestamp": "2026-06-18T10:00:00Z",
            },
            "entities": {
                "uuid-1": {
                    "lower-only": {"value": "must remain covered"},
                }
            },
        }
    )
    m1.load_transport(
        {
            "m1": {
                "id": "cccccccc-cccc-4ccc-8ccc-cccccccccccc",
                "version": "2.0",
                "timestamp": "2026-06-18T11:00:00Z",
            },
            "entities": {
                "uuid-1": {
                    m1.ENTITY_TOMBSTONE: {"entity": True},
                }
            },
        }
    )

    m1.target_entity("uuid-1")
    m1.set_aspect("upper", {"value": "visible"})

    assert m1.has_entity("uuid-1")
    assert m1.get_aspect("upper") == {"value": "visible"}
    assert m1.get_aspect("lower-only") is None

    D = m1.save_m1(tmp_path / "snapshot.m1", "S!")
    assert D["entities"]["uuid-1"] == {
        "upper": {"value": "visible"},
    }


def test_entity_tombstone_amend_replaces_existing_entity_content(tmp_path):
    m1.reset()
    p = tmp_path / "working.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "dddddddd-dddd-4ddd-8ddd-dddddddddddd",
                    "version": "2.0",
                    "timestamp": "2026-06-18T10:00:00Z",
                },
                "entities": {
                    "uuid-1": {
                        "a": {"value": 1},
                        "b": {"value": 2},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.target_entity("uuid-1")
    m1.tombstone_entity()
    D = m1.save_m1(p, "O+")

    assert D["entities"]["uuid-1"] == {
        m1.ENTITY_TOMBSTONE: {"entity": True},
    }


def test_ordinary_amend_reintroduces_entity_without_tombstone_contradiction(tmp_path):
    m1.reset()
    p = tmp_path / "working.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "dededede-dede-4ded-8ded-dededededede",
                    "version": "2.0",
                    "timestamp": "2026-06-18T10:00:00Z",
                },
                "entities": {
                    "uuid-1": {
                        m1.ENTITY_TOMBSTONE: {"entity": True},
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.target_entity("uuid-1")
    m1.set_aspect("a", {"value": "back"})
    D = m1.save_m1(p, "O+")

    assert D["entities"]["uuid-1"] == {
        "a": {"value": "back"},
    }


def test_tombstone_aspect_is_intention_revealing_alias():
    m1.reset()
    m1.target_entity("uuid-1")
    m1.tombstone_aspect("a")

    assert m1.get_overlay()["entities"] == {
        "uuid-1": {"a": None},
    }


def test_overlay_load_tombstone_invalidates_cached_ordinary_aspects():
    m1.reset()
    m1.target_entity("uuid-1")
    m1.set_aspect("a", {"value": 1})
    assert m1.get_aspect("a") == {"value": 1}

    m1.load_transport(
        {
            "m1": {
                "id": "abababab-abab-4aba-8aba-abababababab",
                "version": "2.0",
                "timestamp": "2026-06-18T10:00:00Z",
            },
            "entities": {
                "uuid-1": {
                    m1.ENTITY_TOMBSTONE: {"entity": True},
                }
            },
        },
        flags="O+",
    )

    assert m1.get_aspect("a") is None
    assert not m1.has_entity("uuid-1")


def test_save_normalizes_direct_tombstone_and_ordinary_aspect_contradiction(tmp_path):
    m1.reset()
    m1.target_entity("uuid-1")
    m1.set_aspect("a", {"value": 1})
    m1.set_aspect(m1.ENTITY_TOMBSTONE, {"entity": True})

    D = m1.save_m1(tmp_path / "normalized.m1", "O!")

    assert D["entities"]["uuid-1"] == {
        m1.ENTITY_TOMBSTONE: {"entity": True},
    }


def test_omit_aspect_and_entity_filter_overlay_saves(tmp_path):
    m1.reset()
    m1.target_entity("uuid-1")
    m1.set_aspect("a", {"value": 1})
    m1.set_aspect("b", {"value": 2})
    m1.omit_aspect("a")
    m1.target_entity("uuid-2")
    m1.set_aspect("a", {"value": 3})
    m1.omit_entity()

    assert m1.get_omissions() == {
        "entities": ["uuid-2"],
        "aspects": {"uuid-1": ["a"]},
    }

    D = m1.save_m1(tmp_path / "overlay.m1", "O!")
    assert D["entities"] == {
        "uuid-1": {"b": {"value": 2}},
    }
    assert m1.get_overlay()["entities"]["uuid-1"]["a"] == {"value": 1}


def test_omissions_remove_content_from_overlay_and_snapshot_amend_bases(tmp_path):
    for flags in ("O+", "S+"):
        m1.reset()
        p = tmp_path / f"{flags}.m1"
        p.write_text(
            json.dumps(
                {
                    "m1": {
                        "id": f"eeeeeeee-eeee-4eee-8eee-eeeeeeeeeee{flags[0].lower()}",
                        "version": "2.0",
                        "timestamp": "2026-06-18T10:00:00Z",
                    },
                    "entities": {
                        "uuid-1": {
                            "a": {"value": 1},
                            "b": {"value": 2},
                        },
                        "uuid-2": {
                            "a": {"value": 3},
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        if flags == "S+":
            m1.load_m1(p)

        m1.target_entity("uuid-1")
        m1.omit_aspect("a")
        m1.omit_entity("uuid-2")
        D = m1.save_m1(p, flags)

        assert D["entities"] == {
            "uuid-1": {"b": {"value": 2}},
        }


def test_clear_overlay_also_clears_save_omissions():
    m1.reset()
    m1.target_entity("uuid-1")
    m1.set_aspect("a", {"value": 1})
    m1.omit_aspect("a")
    m1.omit_entity()

    m1.clear_overlay()

    assert m1.get_omissions() == {"entities": [], "aspects": {}}


def test_omit_entity_also_removes_its_table_entry_when_tables_are_saved(tmp_path):
    m1.reset()
    p = tmp_path / "table.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "id": "ffffffff-ffff-4fff-8fff-ffffffffffff",
                    "version": "2.0",
                    "timestamp": "2026-06-18T10:00:00Z",
                },
                "entities": {
                    "uuid-1": {"a": {"value": 1}},
                },
                "table": {
                    "uuid-1": [{"type": "url", "url": "https://example.com/"}],
                },
            }
        ),
        encoding="utf-8",
    )
    m1.target_entity("uuid-1")
    m1.omit_entity()

    D = m1.save_m1(p, "O+t")

    assert "uuid-1" not in D["entities"]
    assert "uuid-1" not in D["table"]
