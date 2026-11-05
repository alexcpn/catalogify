---
type: Module
title: console-options (terminal options editor)
description: The options editor in the mitmproxy terminal UI. It lists every option, edits values in place where it can, shows help, and refreshes when options change.
resource: https://github.com/mitmproxy/mitmproxy/blob/main/mitmproxy/tools/console/options.py
tags: [console, options, ui, python]
source_files:
  - mitmproxy/tools/console/options.py
timestamp: 2024-08-14T17:02:14+02:00
generated_by: catalogify/0.11.0
open_questions:
  - "Which option types can be edited in place, and are the rules in can_edit_inplace() the intended set or a limitation of the urwid widgets?"
---

# Responsibilities

Shows the option registry as a list inside the terminal UI. `OptionListWalker`
supplies rows, `OptionItem` renders each one and `OptionsList` handles key
input. `OptionHelp` shows the help text of the focused option. The top-level
`Options` widget (a `urwid.Pile`) assembles the list and the help panel.
`can_edit_inplace` decides whether an option can be changed in the list
itself, and `OptionListWalker` connects to `master.options.changed` so rows are
redrawn when a value changes from elsewhere (for example the web UI or an addon).

# Interfaces

| Symbol | Purpose |
| --- | --- |
| `Options` | The options pane; a `urwid.Pile` implementing the layout widget protocol. |
| `OptionsList` | The list of options, with key handling and a save-config action. |
| `OptionListWalker` | Supplies rows, focus and editing state to the list. |
| `OptionItem` | Renders one option row. |
| `OptionHelp` | Shows the help text of the focused option. |
| `can_edit_inplace` | Decides whether an option can be edited in the row. |
| `fcol` | Formats a column of fixed width. |

# Dependencies

- Internal: [optmanager](optmanager.md) (`changed` signal, option table); the
  console master in `mitmproxy/tools/console/master.py` subscribes to options.
- Internal: [options](options.md) provides the option set shown here.
- External: `urwid`.

# Key files

- `mitmproxy/tools/console/options.py` - the widgets; `OptionListWalker` is the one to read first.

# Gotchas

- The pane must be recreated or refreshed when addons add options after it was
  built. Commit `bd7069a9` (`#3147`) fixed this by making the option table emit
  `changed` on `add_option` and by recreating the pane on that signal. Before
  it, options added by later addons never appeared in the console.

# Citations

- `bd7069a9` - Adjust options when changed (#3147).
