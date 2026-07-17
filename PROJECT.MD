# Dataset Viewer

Dataset Viewer is a visual workspace for planning and inspecting the JSON datasets that will train private, tool-capable language models. The project lives at `/home/kim/projects/json_data_viewer`.

The ambition is practical: make late-night coding sessions feel focused and enjoyable while we turn well-organised datasets into GGUF models for many different projects. GGUF creation itself is deliberately outside this repository; Dataset Viewer exists to make the preparation stage clear, visible, and repeatable.

## Visual direction

The interface should feel like a calm, capable workstation after dark:

- A black background, luminous green grid, and subtle glow.
- Big, clear text that remains easy to scan during long coding sessions.
- Dataset nodes with the familiar spatial feel of a node editor, but arranged as a deliberately linear training flow.
- A minimal interface that keeps attention on the datasets rather than browser chrome or complicated controls.

## Current status

The interface is considered visually complete for this milestone. The black-and-green studio aesthetic, compact Bootstrap-icon canvas controls, project dashboard, and project actions should be treated as the approved baseline; further work should preserve this calm, canvas-first layout.

## What has been achieved

`index.html` now provides a local visual canvas for the initial dataset flow:

`root.json → tools_sqlite.json → tools_vision.json → tools_salience.json`

Each dataset node can be:

- Dragged into a useful position on the grid.
- Renamed with a right click.
- Hovered to see how many training entries its JSON file currently contains.

The canvas also supports mouse-wheel zooming, `+`/`-` keyboard zoom shortcuts, middle-mouse panning, and a **Centre root** control. **New project** starts a clean grid with a centred `root.json` node. **Load project** presents the saved manifests from `projects/`, newest first. **Save project** writes the dataset list and every node position, zoom level, camera position, and selected node into that project's JSON manifest.

The active header identifies the client and project file, shows corpus health (entry total and unavailable-file count), and makes unsaved changes obvious. **Project details** records the client name, model purpose, target GGUF/model name, notes, and last manifest modification time. Dataset nodes show compact entry-count and source-path badges. The project picker supports live search, **Save as…** duplicates a workspace under a new manifest name, and **Reveal manifest** opens the active manifest's folder.

`server.py` serves the workspace locally and exposes small, restricted endpoints for project loading/saving, manifest reveal, and opening declared JSON files in FeatherPad.

## Projects, configuration, and file lifecycle

`projects/` holds project manifests. The active manifest is selected by `last_project` in `config.json`; the vanilla starting set is `projects/default.json`. A manifest contains the hard-coded absolute paths to its dataset files, so a project can reference JSON files on other mounted drives without moving them into this repository.

`projects/test.json` is a deliberately small switching fixture: it contains only `test.json`, which has one example. It is useful for checking that **Load project** swaps the canvas and its persisted camera/layout state correctly.

When the Python server loads a manifest, it reads each listed JSON file and calculates its entry count. A missing, unreadable, or invalid file is silently skipped and increments the server's `error_count`; the remaining valid datasets still load normally. Only datasets declared in the active manifest may be opened in the configured editor.

`config.json` also sets the editor command and the active CSS theme. The current green theme is `css/green-grid.css`; `css/blue-grid.css` uses the same variable-driven design with a blue grid and accent colour.

The `ui_layout` object in `config.json` controls the placement of the interface zones. The default studio arrangement is `top-left` identity, `top-right` health, a compact `bottom-left` canvas-control cluster, and `bottom-right` project actions. Alternative supported values include `left-dock` and `top-left` for controls, plus `bottom-left` for project actions. Refresh the browser after editing these values.

**File creation is intentionally not implemented yet.** The toolbar therefore says **Add visual node**. It creates a diagram-only note and never pretends that a JSON dataset file exists. Real datasets are added by creating a valid JSON file and then declaring its path in the chosen project manifest.

## Dataset responsibilities

- `root.json` defines the model's purpose, origins, limitations, and foundational behaviour.
- `tools_sqlite.json` collects grounded SQLite tool-use examples for `data.db`.
- `tools_vision.json` is reserved for future vision tool-use examples.
- `tools_salience.json` is reserved for future prioritisation and salience examples.

Every dataset should have one explicit purpose and a consistent response/tool-call pattern before it is expanded substantially.

## Editor opening flow

Double-clicking a manifest-declared dataset node opens its declared path through the editor configured in `config.json`. The browser keeps the clicked node intact through selection so the double-click event reaches the local server; the server then validates the dataset id against the active manifest before it invokes the configured editor command.

## Concerns and deliberate limits

- Project manifests can use absolute dataset paths for multiple drives or project-root-relative paths such as `data/root.json`. A project copied to another machine will still need any absolute paths updated.
- Saving to an existing project name replaces that manifest. There is no overwrite confirmation, backup, undo, or version history yet.
- Dataset files are counted and parsed, but their training-record structure is not deeply validated. A valid JSON file can still contain unsuitable training data.
- Unreadable files are intentionally skipped so that the remaining corpus stays usable. The health strip reports the count, but it does not yet identify the individual failed paths in the interface.
- `Reveal manifest` relies on `xdg-open`, and FeatherPad opening relies on the configured editor command being available on the local system.
- Configuration remains intentionally file-based. `config.json` is the source of truth for theme, editor, active project, and layout zones; there is no configuration screen.

## Most useful next milestones

1. Add a project-safe dataset attachment workflow that creates or selects real JSON files, replacing the temporary visual-only-node limitation when ready.
2. Add per-file validation feedback: invalid JSON, duplicate dataset ids, missing paths, schema/record-shape warnings, and a visible failed-file list.
3. Estimate corpus size and token count, then surface it in the existing health strip.
4. Add safe saving: overwrite confirmation, automatic timestamped backups, and/or manifest revision history.
5. Add a small test suite for manifest loading, saving, path failures, editor command construction, and UI project switching.

## Start the project

From a terminal:

```bash
cd /home/kim/projects/json_data_viewer
python3 server.py
```

Then open [http://127.0.0.1:8000](http://127.0.0.1:8000) in a browser. FeatherPad must be installed and available as `featherpad` for double-click file opening to work.

## Running server note

The **Load project** dialog scans `/home/kim/projects/json_data_viewer/projects` every time it opens. Newly saved or manually added project manifests therefore appear without restarting `server.py`.

When changing `index.html`, CSS, dataset JSON, or project manifests, refresh the browser page. When changing `server.py` itself, stop the existing process with `Ctrl+C` in the terminal that runs it, then start it again with `python3 server.py` so Python loads the updated code.

## GitHub handoff checklist

- Do not commit private client datasets, absolute paths that reveal sensitive storage locations, or generated `__pycache__/` files.
- Keep `projects/test.json` and `test.json` as a small public switching fixture.
- Before publishing, confirm the default project loads, the test project loads one node, save/load preserves the canvas state, and a double-click opens a manifest-declared dataset in the configured editor.
