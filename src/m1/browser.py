import json
import re
import tkinter
from pathlib import Path
from tkinter import filedialog
from tkinter import ttk

import lionscliapp as app

import m1


ROOT = "ROOT"
FILTER_TAGS = "FILTER_TAGS"
FILTER_TITLE = "FILTER_TITLE"
FILTER_NAME = "FILTER_NAME"
ENTITY = "ENTITY"
ASPECT = "ASPECT"
STATUS = "STATUS"
ENTITY_ROWS = "ENTITY_ROWS"
ASPECT_ROWS = "ASPECT_ROWS"
INCLUDE_LINKS = "INCLUDE_LINKS"
MISTAGGED_COMPAT = "MISTAGGED_COMPAT"

kBASIC = "tag:m1lattice.net,2026:aspect/basic"
kLINK = "tag:m1lattice.net,2026:aspect/link"
kMISTAGGED_BASIC = "tag:m1lattice.net,2026/aspect/basic"
kMISTAGGED_LINK = "tag:m1lattice.net,2026/aspect/link"
kUUID_RE = re.compile(r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b")


g = {
    ROOT: None,
    FILTER_TAGS: "",
    FILTER_TITLE: "",
    FILTER_NAME: "",
    ENTITY: None,
    ASPECT: None,
    STATUS: "Ready.",
    ENTITY_ROWS: [],
    ASPECT_ROWS: [],
    INCLUDE_LINKS: True,
    MISTAGGED_COMPAT: False,
}

widgets = {}


def main():
    app.reset()
    app.declare_app("m1-browser", "0.1.0")
    app.describe_app("Browse and import collected M1 transport data.")
    app.declare_projectdir(".m1-browser")
    app.set_flag("search_upwards_for_project_dir", True)
    app.declare_key("startup.input", "")
    app.describe_key("startup.input", "Optional initial file or directory to import on launch.")
    app.declare_cmd("", cmd_browse)
    app.declare_cmd("browse", cmd_browse)
    app.describe_cmd("browse", "Open the M1 browser GUI.")
    app.main()


def cmd_browse():
    build_ui()
    import_initial_path_if_present()
    refresh_everything()
    g[ROOT].mainloop()


def build_ui():
    g[ROOT] = tkinter.Tk()
    g[ROOT].title("M1 Browser")
    g[ROOT].geometry("1380x860")
    g[ROOT].option_add("*tearOff", 0)
    g[ROOT].columnconfigure(0, weight=1)
    g[ROOT].rowconfigure(1, weight=1)

    style = ttk.Style()
    if "clam" in style.theme_names():
        style.theme_use("clam")

    top = ttk.Frame(g[ROOT], padding=10)
    top.grid(row=0, column=0, sticky="ew")
    top.columnconfigure(4, weight=1)
    top.columnconfigure(6, weight=1)
    top.columnconfigure(8, weight=1)

    widgets["import_files"] = ttk.Button(top, text="Import Files", command=handle_when_user_clicks_import_files_button)
    widgets["import_files"].grid(row=0, column=0, padx=(0, 8), pady=(0, 8), sticky="w")

    widgets["import_dir"] = ttk.Button(top, text="Import Folder", command=handle_when_user_clicks_import_folder_button)
    widgets["import_dir"].grid(row=0, column=1, padx=(0, 8), pady=(0, 8), sticky="w")

    widgets["reset"] = ttk.Button(top, text="Reset Claimspace", command=handle_when_user_clicks_reset_button)
    widgets["reset"].grid(row=0, column=2, padx=(0, 12), pady=(0, 8), sticky="w")

    ttk.Label(top, text="Tags contain").grid(row=0, column=3, padx=(0, 6), pady=(0, 8), sticky="e")
    widgets["filter_tags_var"] = tkinter.StringVar()
    widgets["filter_tags_var"].trace_add("write", handle_when_filter_text_changes)
    widgets["filter_tags_entry"] = ttk.Entry(top, textvariable=widgets["filter_tags_var"])
    widgets["filter_tags_entry"].grid(row=0, column=4, padx=(0, 8), pady=(0, 8), sticky="ew")

    ttk.Label(top, text="Title contains").grid(row=0, column=5, padx=(0, 6), pady=(0, 8), sticky="e")
    widgets["filter_title_var"] = tkinter.StringVar()
    widgets["filter_title_var"].trace_add("write", handle_when_filter_text_changes)
    widgets["filter_title_entry"] = ttk.Entry(top, textvariable=widgets["filter_title_var"])
    widgets["filter_title_entry"].grid(row=0, column=6, padx=(0, 8), pady=(0, 8), sticky="ew")

    ttk.Label(top, text="Name contains").grid(row=0, column=7, padx=(0, 6), pady=(0, 8), sticky="e")
    widgets["filter_name_var"] = tkinter.StringVar()
    widgets["filter_name_var"].trace_add("write", handle_when_filter_text_changes)
    widgets["filter_name_entry"] = ttk.Entry(top, textvariable=widgets["filter_name_var"])
    widgets["filter_name_entry"].grid(row=0, column=8, pady=(0, 8), sticky="ew")

    body = ttk.Panedwindow(g[ROOT], orient="horizontal")
    body.grid(row=1, column=0, sticky="nsew", padx=10, pady=(0, 10))

    left = ttk.Frame(body, padding=8)
    left.columnconfigure(0, weight=1)
    left.rowconfigure(1, weight=3)
    left.rowconfigure(3, weight=2)
    ttk.Label(left, text="Entities").grid(row=0, column=0, sticky="w")
    widgets["include_links_var"] = tkinter.BooleanVar(value=True)
    widgets["include_links_var"].trace_add("write", handle_when_include_links_changes)
    widgets["include_links"] = ttk.Checkbutton(left, text="Include Links", variable=widgets["include_links_var"])
    widgets["include_links"].grid(row=0, column=1, sticky="e", padx=(8, 0))
    widgets["mistagged_compat_var"] = tkinter.BooleanVar(value=False)
    widgets["mistagged_compat_var"].trace_add("write", handle_when_mistagged_compat_changes)
    widgets["mistagged_compat"] = ttk.Checkbutton(
        left,
        text="Mis-tagged compat mode",
        variable=widgets["mistagged_compat_var"],
    )
    widgets["mistagged_compat"].grid(row=0, column=2, sticky="e", padx=(8, 0))
    widgets["entity_list"] = tkinter.Listbox(left, exportselection=False)
    widgets["entity_list"].grid(row=1, column=0, columnspan=3, sticky="nsew")
    widgets["entity_list"].bind("<<ListboxSelect>>", handle_when_user_selects_entity)
    ttk.Label(left, text="Links").grid(row=2, column=0, sticky="w", pady=(10, 0))
    widgets["links_text"] = tkinter.Text(left, wrap="word", height=14)
    widgets["links_text"].grid(row=3, column=0, columnspan=3, sticky="nsew")
    body.add(left, weight=4)

    mid = ttk.Frame(body, padding=8)
    mid.columnconfigure(0, weight=1)
    mid.rowconfigure(1, weight=1)
    ttk.Label(mid, text="Aspects").grid(row=0, column=0, sticky="w")
    widgets["aspect_list"] = tkinter.Listbox(mid, exportselection=False)
    widgets["aspect_list"].grid(row=1, column=0, sticky="nsew")
    widgets["aspect_list"].bind("<<ListboxSelect>>", handle_when_user_selects_aspect)
    body.add(mid, weight=2)

    right = ttk.Frame(body, padding=8)
    right.columnconfigure(0, weight=1)
    right.rowconfigure(1, weight=3)
    right.rowconfigure(3, weight=2)
    ttk.Label(right, text="Latest Aspect Claim").grid(row=0, column=0, sticky="w")
    widgets["detail_text"] = tkinter.Text(right, wrap="word")
    widgets["detail_text"].grid(row=1, column=0, sticky="nsew")
    ttk.Label(right, text="Sources").grid(row=2, column=0, sticky="w", pady=(10, 0))
    widgets["sources_text"] = tkinter.Text(right, wrap="word", height=10)
    widgets["sources_text"].grid(row=3, column=0, sticky="nsew")
    body.add(right, weight=5)

    status = ttk.Frame(g[ROOT], padding=(10, 0, 10, 10))
    status.grid(row=2, column=0, sticky="ew")
    widgets["status_var"] = tkinter.StringVar(value=g[STATUS])
    widgets["status"] = ttk.Label(status, textvariable=widgets["status_var"])
    widgets["status"].grid(row=0, column=0, sticky="w")

    configure_guid_tags("detail_text")
    configure_guid_tags("sources_text")
    configure_link_tags("links_text")


def import_initial_path_if_present():
    p = app.ctx["startup.input"]
    if not p:
        return
    p = Path(p)
    if not p.exists():
        set_status("Initial path not found: %s" % p)
        return
    import_path(p)


def handle_when_user_clicks_import_files_button():
    paths = filedialog.askopenfilenames(
        title="Import M1 files",
        filetypes=[("M1 transport files", "*.m1"), ("JSON files", "*.json"), ("All files", "*.*")],
    )
    if not paths:
        return
    import_paths([Path(p) for p in paths])


def handle_when_user_clicks_import_folder_button():
    s = filedialog.askdirectory(title="Import a folder of M1 files")
    if not s:
        return
    import_path(Path(s))


def handle_when_user_clicks_reset_button():
    m1.reset()
    g[ENTITY] = None
    g[ASPECT] = None
    set_status("Claimspace reset.")
    refresh_everything()


def handle_when_filter_text_changes(*_args):
    g[FILTER_TAGS] = widgets["filter_tags_var"].get().strip()
    g[FILTER_TITLE] = widgets["filter_title_var"].get().strip()
    g[FILTER_NAME] = widgets["filter_name_var"].get().strip()
    refresh_entity_list()
    refresh_links_text()


def handle_when_include_links_changes(*_args):
    g[INCLUDE_LINKS] = bool(widgets["include_links_var"].get())
    refresh_entity_list()


def handle_when_mistagged_compat_changes(*_args):
    g[MISTAGGED_COMPAT] = bool(widgets["mistagged_compat_var"].get())
    refresh_entity_list()


def handle_when_user_selects_entity(_event):
    entity_id = get_selected_row_value("entity_list", ENTITY_ROWS)
    g[ENTITY] = entity_id
    g[ASPECT] = None
    refresh_aspect_list()
    refresh_detail_panes()
    refresh_links_text()


def handle_when_user_selects_aspect(_event):
    aspect_id = get_selected_row_value("aspect_list", ASPECT_ROWS)
    g[ASPECT] = aspect_id
    refresh_detail_panes()


def import_path(path):
    if path.is_dir():
        import_paths(sorted(path.rglob("*.m1")))
        return
    import_paths([path])


def import_paths(paths):
    n_loaded = 0
    n_failed = 0
    for path in paths:
        try:
            m1.load_file(path)
            n_loaded += 1
        except Exception as e:
            n_failed += 1
            set_status("Import error for %s: %s" % (path.name, e))
    if n_failed == 0:
        set_status("Imported %d file(s)." % n_loaded)
    else:
        set_status("Imported %d file(s), %d failed." % (n_loaded, n_failed))
    refresh_everything()


def refresh_everything():
    refresh_entity_list()
    refresh_aspect_list()
    refresh_detail_panes()
    refresh_links_text()


def refresh_entity_list():
    rows = get_filtered_entities()
    g[ENTITY_ROWS] = rows
    replace_listbox("entity_list", [row["label"] for row in rows])
    entity_ids = [row["entity_id"] for row in rows]
    if g[ENTITY] is None:
        g[ENTITY] = entity_ids[0] if entity_ids else None
    select_listbox_row("entity_list", ENTITY_ROWS, g[ENTITY])
    update_hidden_entity_status(entity_ids)


def refresh_aspect_list():
    if not g[ENTITY]:
        g[ASPECT_ROWS] = []
        replace_listbox("aspect_list", [])
        return
    aspect_ids = sorted(m1.all_aspects(g[ENTITY]))
    g[ASPECT_ROWS] = [{"aspect_id": aspect_id, "label": aspect_id} for aspect_id in aspect_ids]
    replace_listbox("aspect_list", [row["label"] for row in g[ASPECT_ROWS]])
    if g[ASPECT] not in aspect_ids:
        g[ASPECT] = aspect_ids[0] if aspect_ids else None
    select_listbox_row("aspect_list", ASPECT_ROWS, g[ASPECT])


def refresh_detail_panes():
    replace_text("detail_text", build_detail_text())
    replace_text("sources_text", build_sources_text())


def refresh_links_text():
    replace_links_text("links_text", build_link_rows())


def build_detail_text():
    if not g[ENTITY]:
        return "No entity selected."
    if not g[ASPECT]:
        return "No aspect selected."
    claim = m1.get_latest_aspect(g[ENTITY], g[ASPECT])
    if claim is None:
        return "No claim found."
    D = {
        "entity_id": claim["entity_id"],
        "aspect_id": claim["aspect_id"],
        "source_hash": claim.get("source_hash"),
        "seq": claim.get("seq"),
        "aspect": claim["aspect"],
    }
    return json.dumps(D, indent=2, ensure_ascii=False)


def build_sources_text():
    if not g[ENTITY]:
        return "No entity selected."
    L = []
    for source_hash in m1.get_entity_sources(g[ENTITY]):
        src = m1.get_source(source_hash)
        if src is None:
            continue
        L.append(
            {
                "hash": source_hash,
                "created": src.get("created"),
                "title": src.get("title"),
                "paths": src.get("paths", []),
            }
        )
    return json.dumps(L, indent=2, ensure_ascii=False)


def build_link_rows():
    if not g[ENTITY]:
        return []
    rows = []
    here = get_entity_label(g[ENTITY])
    for link_id in sorted(m1.all_entities(), key=get_entity_label):
        claim = get_link_aspect(link_id)
        if claim is None:
            continue
        D = claim["aspect"]
        src = D.get("from")
        dst = D.get("to")
        rel = D.get("typehint") or get_entity_label(link_id)
        if src == g[ENTITY]:
            rows.append(
                {
                    "direction": "out",
                    "here_label": here,
                    "link_id": link_id,
                    "relation": rel,
                    "other_id": dst,
                    "other_label": get_entity_label(dst) if m1.has_entity(dst) else dst,
                    "known": m1.has_entity(dst),
                }
            )
        elif dst == g[ENTITY]:
            rows.append(
                {
                    "direction": "in",
                    "here_label": here,
                    "link_id": link_id,
                    "relation": rel,
                    "other_id": src,
                    "other_label": get_entity_label(src) if m1.has_entity(src) else src,
                    "known": m1.has_entity(src),
                }
            )
    return rows


def get_filtered_entities():
    rows = []
    for entity_id in sorted(m1.all_entities(), key=get_entity_label):
        if not g[INCLUDE_LINKS] and has_link_aspect(entity_id):
            continue
        label = get_entity_label(entity_id)
        tags = " ".join(get_basic_tags(entity_id)).casefold()
        basic_aspects = get_basic_aspects(entity_id)
        titles = [str(claim["aspect"].get("title", "")).casefold() for claim in basic_aspects]
        names = [str(claim["aspect"].get("name", "")).casefold() for claim in basic_aspects]
        if g[FILTER_TAGS].casefold() not in tags:
            continue
        if g[FILTER_TITLE] and not any(g[FILTER_TITLE].casefold() in title for title in titles):
            continue
        if g[FILTER_NAME] and not any(g[FILTER_NAME].casefold() in name for name in names):
            continue
        rows.append({"entity_id": entity_id, "label": label})
    return rows


def get_basic_aspect(entity_id):
    return m1.get_latest_aspect(entity_id, kBASIC)


def has_link_aspect(entity_id):
    return get_link_aspect(entity_id) is not None


def get_link_aspect(entity_id):
    aspect_ids = [kLINK]
    if g[MISTAGGED_COMPAT]:
        aspect_ids.append(kMISTAGGED_LINK)
    for aspect_id in aspect_ids:
        claim = m1.get_latest_aspect(entity_id, aspect_id)
        if claim is not None and isinstance(claim["aspect"], dict):
            return claim
    return None


def get_basic_aspects(entity_id):
    aspect_ids = [kBASIC]
    if g[MISTAGGED_COMPAT]:
        aspect_ids.append(kMISTAGGED_BASIC)
    return [
        claim
        for aspect_id in aspect_ids
        if (claim := m1.get_latest_aspect(entity_id, aspect_id)) is not None
        and isinstance(claim["aspect"], dict)
    ]


def get_basic_tags(entity_id):
    tags = []
    for claim in get_basic_aspects(entity_id):
        claim_tags = claim["aspect"].get("tags", [])
        if isinstance(claim_tags, list):
            tags.extend(str(tag) for tag in claim_tags)
    return tags


def get_entity_label(entity_id):
    if not m1.has_entity(entity_id):
        return entity_id
    claim = get_basic_aspect(entity_id)
    if claim is None or not isinstance(claim["aspect"], dict):
        return entity_id
    if claim["aspect"].get("title"):
        return claim["aspect"]["title"]
    if claim["aspect"].get("name"):
        return claim["aspect"]["name"]
    return entity_id


def get_selected_row_value(name, rows_name):
    w = widgets[name]
    sel = w.curselection()
    if not sel:
        return None
    i = sel[0]
    if i >= len(g[rows_name]):
        return None
    row = g[rows_name][i]
    if rows_name == ENTITY_ROWS:
        return row["entity_id"]
    return row["aspect_id"]


def replace_listbox(name, L):
    w = widgets[name]
    w.delete(0, tkinter.END)
    for s in L:
        w.insert(tkinter.END, s)


def select_listbox_row(name, rows_name, value):
    w = widgets[name]
    w.selection_clear(0, tkinter.END)
    if not value:
        return
    for i, row in enumerate(g[rows_name]):
        if rows_name == ENTITY_ROWS and row["entity_id"] == value:
            w.selection_set(i)
            w.see(i)
            return
        if rows_name == ASPECT_ROWS and row["aspect_id"] == value:
            w.selection_set(i)
            w.see(i)
            return


def replace_text(name, s):
    w = widgets[name]
    w.delete("1.0", tkinter.END)
    w.insert("1.0", s)
    apply_guid_tags(name)


def replace_links_text(name, rows):
    w = widgets[name]
    clear_link_tags(name)
    w.delete("1.0", tkinter.END)
    if not rows:
        w.insert("1.0", "No links for this entity.")
        return
    for row in rows:
        add_link_row(w, row)


def add_link_row(w, row):
    if row["direction"] == "out":
        w.insert(tkinter.END, row["here_label"])
        w.insert(tkinter.END, " -> ")
        rel_start = w.index("end-1c")
        w.insert(tkinter.END, row["relation"])
        rel_end = w.index("end-1c")
        w.insert(tkinter.END, " -> ")
        other_start = w.index("end-1c")
        w.insert(tkinter.END, row["other_label"])
        other_end = w.index("end-1c")
    else:
        w.insert(tkinter.END, row["here_label"])
        w.insert(tkinter.END, " <- ")
        rel_start = w.index("end-1c")
        w.insert(tkinter.END, row["relation"])
        rel_end = w.index("end-1c")
        w.insert(tkinter.END, " <- ")
        other_start = w.index("end-1c")
        w.insert(tkinter.END, row["other_label"])
        other_end = w.index("end-1c")
    w.insert(tkinter.END, "\n")

    rel_tag = "jump_link__%s" % row["link_id"]
    w.tag_add("jump_link", rel_start, rel_end)
    w.tag_add(rel_tag, rel_start, rel_end)

    if row["known"]:
        entity_tag = "jump_entity__%s" % row["other_id"]
        w.tag_add("jump_entity", other_start, other_end)
        w.tag_add(entity_tag, other_start, other_end)
    else:
        w.tag_add("unknown_link", other_start, other_end)


def set_status(s):
    g[STATUS] = s
    widgets["status_var"].set(s)


def configure_guid_tags(name):
    w = widgets[name]
    w.tag_configure("guid_known", foreground="#1f5aa6", underline=True)
    w.tag_configure("guid_unknown", foreground="#b22222", underline=False)
    w.tag_bind("guid_known", "<Button-1>", handle_when_user_clicks_guid_reference)
    w.tag_bind("guid_known", "<Enter>", handle_when_mouse_enters_clickable_reference)
    w.tag_bind("guid_known", "<Leave>", handle_when_mouse_leaves_clickable_reference)


def configure_link_tags(name):
    w = widgets[name]
    w.tag_configure("jump_link", foreground="#1f5aa6", underline=True)
    w.tag_configure("jump_entity", foreground="#1f5aa6", underline=True)
    w.tag_configure("unknown_link", foreground="#b22222", underline=False)
    w.tag_bind("jump_link", "<Button-1>", handle_when_user_clicks_link_reference)
    w.tag_bind("jump_entity", "<Button-1>", handle_when_user_clicks_link_reference)
    w.tag_bind("jump_link", "<Enter>", handle_when_mouse_enters_clickable_reference)
    w.tag_bind("jump_entity", "<Enter>", handle_when_mouse_enters_clickable_reference)
    w.tag_bind("jump_link", "<Leave>", handle_when_mouse_leaves_clickable_reference)
    w.tag_bind("jump_entity", "<Leave>", handle_when_mouse_leaves_clickable_reference)
    w.tag_raise("jump_link")
    w.tag_raise("jump_entity")


def apply_guid_tags(name):
    w = widgets[name]
    clear_guid_tags(name)
    s = w.get("1.0", "end-1c")
    for m in kUUID_RE.finditer(s):
        start = "1.0 + %d chars" % m.start()
        end = "1.0 + %d chars" % m.end()
        entity_id = m.group(0)
        tag = "guid_known" if m1.has_entity(entity_id) else "guid_unknown"
        tag_name = "%s__%s__%d" % (tag, entity_id, m.start())
        w.tag_add(tag, start, end)
        w.tag_add(tag_name, start, end)


def clear_guid_tags(name):
    w = widgets[name]
    for tag in w.tag_names():
        if tag.startswith("guid_known__") or tag.startswith("guid_unknown__"):
            w.tag_delete(tag)
    w.tag_remove("guid_known", "1.0", tkinter.END)
    w.tag_remove("guid_unknown", "1.0", tkinter.END)


def clear_link_tags(name):
    w = widgets[name]
    for tag in w.tag_names():
        if tag.startswith("jump_link__") or tag.startswith("jump_entity__"):
            w.tag_delete(tag)
    w.tag_remove("jump_link", "1.0", tkinter.END)
    w.tag_remove("jump_entity", "1.0", tkinter.END)
    w.tag_remove("unknown_link", "1.0", tkinter.END)


def handle_when_user_clicks_guid_reference(event):
    w = event.widget
    i = w.index("@%d,%d" % (event.x, event.y))
    for tag in w.tag_names(i):
        if tag.startswith("guid_known__"):
            navigate_to_entity(tag.split("__", 2)[1])
            return


def handle_when_user_clicks_link_reference(event):
    w = event.widget
    i = w.index("@%d,%d" % (event.x, event.y))
    for tag in w.tag_names(i):
        if tag.startswith("jump_entity__"):
            navigate_to_entity(tag.split("__", 1)[1])
            return
        if tag.startswith("jump_link__"):
            navigate_to_entity(tag.split("__", 1)[1])
            return


def handle_when_mouse_enters_clickable_reference(event):
    event.widget.configure(cursor="hand2")


def handle_when_mouse_leaves_clickable_reference(event):
    event.widget.configure(cursor="")


def navigate_to_entity(entity_id):
    if not m1.has_entity(entity_id):
        return
    g[FILTER_TAGS] = ""
    g[FILTER_TITLE] = ""
    g[FILTER_NAME] = ""
    widgets["filter_tags_var"].set("")
    widgets["filter_title_var"].set("")
    widgets["filter_name_var"].set("")
    g[ENTITY] = entity_id
    g[ASPECT] = None
    refresh_entity_list()
    refresh_aspect_list()
    refresh_detail_panes()
    refresh_links_text()
    set_status("Navigated to %s" % entity_id)


def update_hidden_entity_status(entity_ids):
    if g[ENTITY] is None:
        return
    if g[ENTITY] in entity_ids:
        return
    if not m1.has_entity(g[ENTITY]):
        return
    set_status("Viewing hidden entity: %s" % get_entity_label(g[ENTITY]))


if __name__ == "__main__":
    main()
