# Ground truth: the terminal at 00:02:42, per Tristan's reading of the frame

From *Install Claude Code and-or the AI Memory Vault*, frame `00-02-42.png`.
A zsh session in a window wider than the picture, so two lines leave the shot
on the right; those are marked CUT and only the visible part is graded.

The deterministic layer is DONE when its console output matches this line for
line: the same characters, the same prompt on the same lines, and the same
lines marked cut.

```
                                            typed?  cut?
Next: Run claude --help to get started      output
⚠ Setup notes:                              output
● Native installation exists but ~/.local/bin is not in your PATH.   output
echo 'export PATH="$HOME/.local/bin:$PATH"' >> ~/.zshrc && source    output  CUT
✅ Installation complete!                    output
[jared@macbook-air ~ % echo 'export PATH="$HOME/.local/bin:$PATH"' >>  typed  CUT
source ~/.zshrc                             output
[jared@macbook-air ~ % cd ~/documents/henry  typed
[jared@macbook-air henry %                   typed
```

Two notes on what is NOT gradeable here, so nobody chases them later.

`⚠`, `●` and `✅` are drawn once each and read by no engine; they cost a
character or two every run and no instrument on this screen can settle them,
because a glyph appearing once has nothing to be compared against.

`source ~/.zshrc` is the tail of the command above it, wrapped by a terminal
whose right-hand columns the recording does not show. Nothing in the frame
proves that -- the missing text is missing -- so it is graded as output, and
the CUT mark on the line above is what says the rest is elsewhere.
