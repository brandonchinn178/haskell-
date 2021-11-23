# Haskell Syntax: Sublime Text syntax definitions for Haskell

## Quickstart

```bash
./generate.sh

ln -sf "${PWD}/src" "${HOME}/Library/Application Support/Sublime Text 3/Packages/Haskell-Syntax"
```

To run syntax tests:

1. Open a separate Sublime Text window (cmd + shift + N)

2. Drag and drop the `Sublime Text 3/Packages/Haskell-Syntax/` from Finder into the new window (just running `subl` on the symlinked folder won't work, as it'll resolve to the original location, not the `~/Library/` location)

3. Open `Haskell-Syntax.sublime-syntax` via Command Prompt (cmd + P)

4. Run build (F7)
