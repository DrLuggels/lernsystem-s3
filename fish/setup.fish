#!/usr/bin/env fish
# Hängt den Befehl `lernen` in fish ein (Symlinks nach ~/.config/fish).
# Vorhandene Dateien werden nur mit `--ersetzen` überschrieben.

set -l hier (path dirname (path resolve (status filename)))
set -l ersetzen (contains -- --ersetzen $argv; and echo ja)

for art in functions completions
    set -l ziel ~/.config/fish/$art/lernen.fish
    mkdir -p ~/.config/fish/$art
    if test -e $ziel -o -L $ziel
        if test "$ersetzen" != ja
            echo "Übersprungen: $ziel existiert schon ("(path resolve $ziel)")."
            echo "  Zum Ersetzen: fish "(status filename)" --ersetzen"
            continue
        end
    end
    ln -sf $hier/$art/lernen.fish $ziel
    echo "Eingehängt: $ziel"
end
