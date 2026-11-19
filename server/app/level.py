"""Level-Logik. Einzige Stelle, an der Schwellen und Aufstiegsregeln stehen."""

SCHWELLEN = {1: 50, 2: 65, 3: 80, 4: 95, 5: 100}
MAX_LEVEL = 5
BEHERRSCHT_AB = 4


def neues_level(level: int, claude_wert: int, user_wert: int) -> int:
    """Eine Stufe hoch, wenn beide Werte die Schwelle des nächsten Levels erreichen."""
    for wert in (claude_wert, user_wert):
        if not 0 <= wert <= 100:
            raise ValueError(f"Wert außerhalb 0–100: {wert}")
    if level >= MAX_LEVEL:
        return level
    schwelle = SCHWELLEN[level + 1]
    if claude_wert >= schwelle and user_wert >= schwelle:
        return level + 1
    return level


def nach_starker_aenderung(level: int) -> int:
    """Die Quelle hat sich inhaltlich stark geändert: eine Stufe zurück."""
    return max(0, level - 1)


def ist_beherrscht(level: int) -> bool:
    return level >= BEHERRSCHT_AB
