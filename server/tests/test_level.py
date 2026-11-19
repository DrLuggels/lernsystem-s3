import pytest

from app import level


def test_schwellen_wie_in_der_spec():
    assert level.SCHWELLEN == {1: 50, 2: 65, 3: 80, 4: 95, 5: 100}


@pytest.mark.parametrize(
    "start, claude, user, erwartet",
    [
        (0, 50, 50, 1),    # beide genau auf der Schwelle
        (0, 49, 100, 0),   # Claude darunter
        (0, 100, 49, 0),   # User darunter
        (0, 100, 100, 1),  # nie mehr als eine Stufe
        (1, 64, 65, 1),
        (1, 65, 65, 2),
        (2, 80, 80, 3),
        (3, 95, 94, 3),
        (3, 95, 95, 4),
        (4, 99, 100, 4),
        (4, 100, 100, 5),
        (5, 100, 100, 5),  # Maximum
        (3, 0, 0, 3),      # kein Abstieg durch schlechte Bewertung
    ],
)
def test_neues_level(start, claude, user, erwartet):
    assert level.neues_level(start, claude, user) == erwartet


@pytest.mark.parametrize("wert", [-1, 101])
def test_werte_ausserhalb_0_bis_100_sind_fehler(wert):
    with pytest.raises(ValueError):
        level.neues_level(0, wert, 50)
    with pytest.raises(ValueError):
        level.neues_level(0, 50, wert)


def test_starke_aenderung_senkt_um_eine_stufe():
    assert level.nach_starker_aenderung(3) == 2
    assert level.nach_starker_aenderung(0) == 0


def test_beherrscht_ab_level_4():
    assert [level.ist_beherrscht(n) for n in range(6)] == [False, False, False, False, True, True]
