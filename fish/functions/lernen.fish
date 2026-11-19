function lernen --description "Lernsystem Semester 3"
    # Der Pfad wird von fish/setup.fish beim Einrichten eingetragen.
    set -l wurzel (path dirname (path dirname (path dirname (path resolve (status filename)))))
    python3 $wurzel/cli/lernen.py $argv
end
