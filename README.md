# tfe

A File Explorer built for the terminal.

**Caution: This project is in its very early stages.**

## Setup
```py
git clone https://github.com/NSPC911/tfe
cd tfe
uv sync
```
## Run
```py
uv run src/main.py
```

## Roadmap

This is a list of features that I plan to add before releasing v1 and where they are inspired from.
- [x] Directory Autocompletion (explorer)
- [x] Button Navigation (explorer)
- [ ] Keyboard Navigation
  - [x] Directory Navigation (explorer)
  - [ ] Others (superfile)
- [ ] Double Click to enter into directories (explorer)
- Configuration (superfile)
  - [x] Base
  - [ ] Schema
  - [x] Extending custom themes via configuration
- [ ] [zoxide](https://github.com/ajeetdsouza/zoxide) support (ranger)<br><sub>There is no command line for tfe, which means it will use keybinds to launch either a modified current folder bar or a panel</sub>
- [x] Previewing image files using [textual-image](https://github.com/lnqs/textual-image) (superfile)<br><sub>Explorer does support image viewing, but this is a TUI, so inspiration is from superfile</sub>
- [x] Previewing directories (superfile)
- [ ] Pinned folder sidebar (superfile)<br><sub>explorer does support pinned sidebar, but it also includes the massive file tree, which I won't add.</sub>
- [ ] Clipboard (superfile)
- [ ] Active and Completed processes (superfile)
- [ ] Actions (explorer)
