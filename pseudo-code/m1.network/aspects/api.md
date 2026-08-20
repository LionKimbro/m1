```
date: 2026-08-20
title: API for m1.network package
```

functions:
  import_file(p)
  import_url(url)

  select_entity(e_id)
  create_entity(flags=None)  # note: if no target file, this is an error; also: returns new UUID
    # supports flag: ["select"]  -- automatically select_entity the newly created entity

  target_file(p)

  set_aspect(a_id, data)
  get_aspect(a_id)
  delete_aspect(a_id)

  load_more(flags=[])  # moderated by global registers & flags;
                       # flag: all  -- maximally read info from table
		               # flag: entity  -- read info just about the selected entity (default scope)
		               # flag: repeat  -- read as long as there is info to be found
		               # flag: retry-rejected -- retry entries previously rejected for redefinition
		               # flag: retry-failed -- retry entries whose previous load attempt failed

  known_entities()  # return list(aspects.keys())
  known_aspects()  # return list(aspects[cur-e_id].keys())

  save_files()  -- save all dirty files
  save_file(p)  -- save just this one dirty file

constants:
  BASIC_ASPECT
  LINK_ASPECT
  LOG_ASPECT

global data:
  aspects  -- {entity-id: {aspect-id: data, ...}, ...}
  sources  -- {entity-id: {aspect-id: document-key, ...}, ...}
  dirty_filepaths  -- {filepath, ...}
  resources  -- {document-key: document-data, ...}
  table  -- {entity-id: [{...table-entry...}, ...], ...]
  g = {
    # selection
    "selected-entity": None,
    "target-file": None,

    # load_more policy
    "load-more-max-files": 10,
    "load-more-stop-after-seconds": 1,

    # last operation result
    "load-more-complete": true/false/None,
    
    <error info>...,  # "last-error", "last-import-info", ...
    <metrics info>...,  # "files-loaded", "files-rejected", "urls-loaded", ...
    ...
  }


document-key format:
  for "file" entries, use the supplied filepath;
  for "url" entries, use the supplied URL

document-data format -- something like:
  {
    "source": <...table-entry...>,
    "data": {...original M1 transport document...} (or None),
    "dirty": False,
    "writable": True,
    "load_attempted": <timestamp>,
    "load_result": None | "LOADED" | "REJECTED" (readable but redefines E/A) | "FAILED" (404, permission denied, invalid JSON, ...),
    "file_info": {...}
    load-error-info,
    ...
  }
  (you may adjust this)


NOTE-1:
* filepaths should be canonicalized before use and storage:
  ---
  from pathlib import Path
  
  def canonical_path(p, flags=None):
      flags = flags or []
      p = Path(p)
  
      if "new" in flags:
          dirpath = p.parent.resolve(strict=True)
          return dirpath / p.name
  
      return p.resolve(strict=True)
  ---

NOTE-2:
* Invariant (pre/post):
  the global data always describes one presently coherent M1 network;
  An import either joins the network completely, or does not join at all;
  An edit changes both the network view and its owning in-memory source document together.

  IMPORT: resource -> validate/stage -> COMMIT WHOLE DOCUMENT
  EDIT: API operation -> owning document + indexes change together

NOTE-3:
* set_aspect(aspect, data)

  if it doesn't exist:
    owner = target-file
    target document changes
    aspects changes
    sources changes
    dirty_filepaths changes

  but if it DOES exist:
    owner = sources[selected_entity][aspect]
    that document changes
    aspects change
    dirty_filepaths change
    (target-file is irrelevant)


internal functions:
  mark_file_dirty(canonical_filepath)):
      resources[canonical_filepath]["dirty"] = True
      dirty_filepaths.add(canonical_filepath)

