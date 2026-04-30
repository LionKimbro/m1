import json

import m1


def test_load_file_collects_aspects_and_sources(tmp_path):
    m1.reset()
    p = tmp_path / "a.m1"
    p.write_text(
        json.dumps(
            {
                "m1": {
                    "version": "2.0",
                    "created": "2026-04-20T10:00:00Z",
                    "title": "A",
                },
                "entities": {
                    "uuid-1": {
                        "tag:m1lattice.net,2026/aspect/basic": {
                            "name": "alpha",
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

    m1.load_file(p)

    assert m1.has_entity("uuid-1")
    assert m1.all_aspects("uuid-1") == [
        "tag:m1lattice.net,2026/aspect/basic",
        "tag:m1lattice.net,2026/aspect/log",
    ]
    hashes = m1.get_entity_sources("uuid-1")
    assert len(hashes) == 1
    src = m1.get_source(hashes[0])
    assert src["paths"] == [str(p.resolve())]


def test_latest_aspect_prefers_newer_created_timestamp(tmp_path):
    m1.reset()
    p1 = tmp_path / "older.m1"
    p2 = tmp_path / "newer.m1"

    p1.write_text(
        json.dumps(
            {
                "m1": {
                    "version": "2.0",
                    "created": "2026-04-20T10:00:00Z",
                },
                "entities": {
                    "uuid-1": {
                        "tag:m1lattice.net,2026/aspect/basic": {
                            "title": "Older Title",
                        }
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
                    "version": "2.0",
                    "created": "2026-04-21T10:00:00Z",
                },
                "entities": {
                    "uuid-1": {
                        "tag:m1lattice.net,2026/aspect/basic": {
                            "title": "Newer Title",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.load_files([p1, p2])
    claim = m1.get_latest_aspect("uuid-1", "tag:m1lattice.net,2026/aspect/basic")

    assert claim["aspect"]["title"] == "Newer Title"
    assert len(m1.get_claims("uuid-1", "tag:m1lattice.net,2026/aspect/basic")) == 2
    assert "source_hash" in claim


def test_latest_aspect_falls_back_to_load_order_when_created_missing(tmp_path):
    m1.reset()
    p1 = tmp_path / "one.m1"
    p2 = tmp_path / "two.m1"

    p1.write_text(
        json.dumps(
            {
                "m1": {
                    "version": "2.0",
                },
                "entities": {
                    "uuid-1": {
                        "tag:m1lattice.net,2026/aspect/basic": {
                            "title": "One",
                        }
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
                    "version": "2.0",
                },
                "entities": {
                    "uuid-1": {
                        "tag:m1lattice.net,2026/aspect/basic": {
                            "title": "Two",
                        }
                    }
                },
            }
        ),
        encoding="utf-8",
    )

    m1.load_files([p1, p2])
    claim = m1.get_latest_aspect("uuid-1", "tag:m1lattice.net,2026/aspect/basic")

    assert claim["aspect"]["title"] == "Two"


def test_duplicate_file_bytes_merge_under_one_source_hash(tmp_path):
    m1.reset()
    p1 = tmp_path / "a.m1"
    p2 = tmp_path / "copy.m1"
    s = json.dumps(
        {
            "m1": {
                "version": "2.0",
                "created": "2026-04-20T10:00:00Z",
            },
            "entities": {
                "uuid-1": {
                    "tag:m1lattice.net,2026/aspect/basic": {
                        "title": "Alpha",
                    }
                }
            },
        }
    )
    p1.write_text(s, encoding="utf-8")
    p2.write_text(s, encoding="utf-8")

    m1.load_files([p1, p2])

    hashes = m1.get_entity_sources("uuid-1")
    assert len(hashes) == 1
    src = m1.get_source(hashes[0])
    assert sorted(src["paths"]) == sorted([str(p1.resolve()), str(p2.resolve())])
    assert len(m1.get_claims("uuid-1", "tag:m1lattice.net,2026/aspect/basic")) == 1


def test_missing_entity_or_aspect_returns_empty_values():
    m1.reset()

    assert m1.all_aspects("missing") == []
    assert m1.all_entities() == []
    assert m1.get_claims("missing", "aspect") == []
    assert m1.get_latest_aspect("missing", "aspect") is None
