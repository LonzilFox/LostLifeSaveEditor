# SOL Save Editor

A Windows desktop editor for **Adobe Flash SharedObject (`.sol`) saves using AMF3**. The initial field catalog covers the `HLB02_Core_1.52` save schema. Other compatible AMF3 files can also be inspected without predefined field labels.

The application uses a dark pink, iOS-inspired theme with Canvas-rendered rounded cards, buttons, inputs, switches, and scrollbars. Its field table uses responsive widths and reserves space for the rightmost status column. It provides an editable, searchable view of the complete save tree. Application-owned controls and dialogs share the same palette; native Windows file pickers follow the operating system theme.

## Features

- Reads standard `TCSO` / AMF3 SharedObject files, including nested objects, arrays, dates, strings, numbers, and Boolean values.
- Categorizes every known top-level field and displays original paths alongside readable descriptions.
- Shows original versus edited values and highlights unsaved changes.
- Supports typed field editing, structured JSON editing, undo/redo, individual reset, and full reset.
- Compares two save files and exports field inventories or differences as CSV.
- Exports/imports a round-trippable JSON representation with a matching SharedObject name check.
- Automatically discovers matching save files in standard Flash Player storage directories on Windows.
- Detects changes to the save made by another process before overwriting.
- Creates timestamped backups before replacement (enabled by default).
- Saves atomically, reparses the bytes, and verifies the saved file on disk.
- Supports keyboard shortcuts: `Ctrl+O` open, `Ctrl+S` save, `Ctrl+Shift+S` save as, `Ctrl+F` search, `Ctrl+Z` undo, `Ctrl+Y` redo.
- Provides an offline validator and command-line save comparison.

The catalog **does not claim to know internal game formulas or maximum values**. Some labels are based on names rather than confirmed runtime behavior. No undocumented progression or content presets are included.

## Requirements

- Windows 10 or Windows 11
- Python 3.10 or later for development mode
- No additional Python packages for development mode (the GUI and rounded widgets use standard-library Tkinter)

## Run

Double-click `run-dev.bat`. Optionally, drag a `.sol` file onto the batch script, or use the **Open SOL** button in the app.

For command-line validation:

```cmd
run-dev.bat --validate "C:\path\to\save.sol"
```

To compare two save files:

```cmd
run-dev.bat "C:\path\to\current.sol" --diff "C:\path\to\previous.sol"
```

## Build a standalone Windows executable

Run **`build-release.bat`**. The script creates its own isolated build environment and installs PyInstaller. After a successful build, the executable is located at:

```text
dist\SOLSaveEditor.exe
```

The executable can run on a compatible Windows PC without a separate Python installation.

## Safety and recovery

**Exit the game before changing a save file.** Otherwise the game may overwrite your modifications with its in-memory state.

An original-file backup is written next to the save in `SOLSaveEditor_Backups` whenever an existing target is replaced. The backup manager can restore a selected backup and preserves an additional copy of the currently active file before restoration.

Out-of-range values can produce unpredictable game behavior. The editor preserves original value types and validates serialization, but format validity **does not guarantee gameplay validity**.

When uploading this repository to GitHub, **do not commit personal `.sol` saves, JSON exports, or generated executables**. These are ignored by the included `.gitignore`.

## Project files

```text
LostLifeSaveEditor/
  main.py
  editor_core.py
  sol_codec.py
  field_catalog.py
  theme.py
  rounded_ui.py
  table_layout.py
  dialogs.py
  run-dev.bat
  build-release.bat
  README.md
  VERSION
  .gitignore
  docs/
    field_manifest.json
    FORMAT.md
  tests/
    test_editor.py
    test_layout.py
```

Only two batch files are provided. Internal filenames and the project directory do not contain release version numbers.

## Testing

```cmd
python -m unittest discover -s tests -v
```

All bundled tests use synthetic save data. No player-provided save is distributed with this project.

## Supported scope

- Input/output: standard AMF3 `TCSO` SOL
- Out of scope: encrypted saves, non-AMF3 files, or externalizable custom AMF objects that need application-specific code
- Release version: `0.0.1`
