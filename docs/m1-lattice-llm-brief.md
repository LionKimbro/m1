```
document-id: m1lattice.spec.core.v3.brief
title: M1 Lattice: Brief of the Core Specification
document-type: brief
purpose: Briefly explain the M1 Lattice: Core Specification, sufficient for causal use
tags: m1lattice m1 core spec specification brief review summary model entity entities aspect table link links
```

# M1 Lattice: LLM Brief

M1 is a deliberately small, extensible ontology for representing knowledge. Its only structural primitive is the **entity**. An entity is anything that needs a stable identity: a person, file, concept, event, relationship, agent, or type. Every entity has one permanent identifier, expressed either as a UUID or a Tag URI. UUID input is normalized to lowercase hyphenated form; Tag URIs are compared as exact strings and must never be rewritten.

## Core model

An entity has no universal record shape beyond its identifier. Meaning is added by attaching **aspects**: identified values that describe a dimension of that entity. Conceptually:

```text
entity ID -> { aspect ID -> JSON value, ... }
```

An aspect is always attached to one entity, has an identifier, and may contain any JSON value (including `null`). The identifier determines how its content is interpreted; consumers, not the core ontology, own that interpretation. An entity may have many aspects, including incomplete or mutually conflicting ones. The presence of an aspect ID asserts that the entity has that aspect; absence is represented by no mapping for that ID.

This makes M1 additive rather than schema-first: use a broadly useful convention where it is enough, and introduce a named, specialized aspect whenever precision or a stronger schema is needed. No implementation, storage layout, global aspect schema, deletion model, merge policy, or location-selection policy is imposed by the core specification.

## Standard aspect conventions

- **Basic aspect** — `tag:m1lattice.net,2026:aspect/basic` supplies a loose, human-friendly layer for generic browsing. Common optional fields are `typehint`, `name`, `title`, `description`, `tags`, `url`, `file`, `image`, `date`, `location`, `notes`, and `hook`. These fields are intentionally non-authoritative; `typehint` (for example `person`, `book`, or `link`) is a presentation and discovery hint, not formal typing. Extra fields are allowed.

- **Link aspect** — `tag:m1lattice.net,2026:aspect/link` turns an ordinary entity into a relationship entity. It requires directional `from` and `to` entity IDs, and may have a formal relationship `type` (itself an entity ID) plus a readable `typehint`. Links have no special primitive status: they are entities, so they can have their own basic, log, or domain-specific aspects. Multiple links may connect the same endpoints.

- **Log aspect** — `tag:m1lattice.net,2026:aspect/log` records append-oriented activity for an entity. Its required `log` array is chronological; each entry requires `timestamp` and `event`, with optional `note`, intentional `agent`, and mechanism `via`. Suggested open-vocabulary events include `CREATED`, `UPDATED`, `ACCESSED`, `DEPRECATED`, and `NOTE`. Logs from sources may be combined, preserving individual entries and removing identical duplicates.

## Tables and resource resolution

A **table** is not part of the lattice ontology. It is an environment-specific lookup layer:

```text
entity ID -> [ resource location, ... ]
```

Each ID may resolve to zero or more locations. Common location objects use `type: "file"` with `path`, or `type: "url"` with `url`; further location types and fields are permitted. Tables let a system find concrete files, URLs, or other resources for an entity, but the consuming application decides which location to use. Direct URLs and paths can also be used as resource references.

## Operational reading rules for an LLM

1. Treat IDs as durable identity, not as mutable names or storage addresses.
2. Treat aspects as the source of all semantics; use the aspect ID to select an interpretation.
3. Read `basic` first for display and coarse discovery, but do not infer strict facts from it when a specialized aspect says more.
4. Recognize an entity as a directed link only when it has the link aspect; then follow `from` to `to` and use `type` if supplied.
5. Preserve unknown aspects and additional fields. They are valid extension points, not malformed data.
6. Keep ambiguity where the model leaves it open; do not invent a universal schema, a preferred resource location, or conflict-resolution semantics.

Minimal M1 support means recognizing and resolving entity IDs, supporting aspects, and recognizing the `basic` and `link` conventions.
