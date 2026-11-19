import pytest

import lernen


@pytest.fixture
def quelle(tmp_path):
    (tmp_path / "cc" / "topics" / "docker" / "01-a").mkdir(parents=True)
    (tmp_path / "cc" / "ABOUT.md").write_text("about")
    (tmp_path / "cc" / "topics" / "docker" / "01-a" / "TOPIC.md").write_text("stoff")
    return tmp_path


def _daten():
    return {
        "faecher": [{"slug": "cc", "name": "Cloud", "about_pfad": "cc/ABOUT.md"}],
        "themen": [{"schluessel": "cc/topics/docker", "fach": "cc", "titel": "Docker"}],
        "eintraege": [{
            "schluessel": "cc/topics/docker/01-a/TOPIC.md#x", "thema": "cc/topics/docker",
            "art": "lernpunkt", "titel": "X", "quellpfad": "cc/topics/docker/01-a/TOPIC.md",
        }],
    }


def test_anreichern_setzt_hashes(quelle):
    daten = lernen.anreichern(_daten(), quelle)
    assert daten["faecher"][0]["about_hash"] == lernen.datei_hash(quelle / "cc" / "ABOUT.md")
    assert len(daten["eintraege"][0]["quell_hash"]) == 16


def test_hash_aendert_sich_mit_dem_inhalt(quelle):
    pfad = quelle / "cc" / "ABOUT.md"
    vorher = lernen.datei_hash(pfad)
    pfad.write_text("anders")
    assert lernen.datei_hash(pfad) != vorher


def test_fehlende_quelle_wird_gemeldet(quelle):
    daten = _daten()
    daten["eintraege"][0]["quellpfad"] = "cc/gibt/es/nicht.md"
    with pytest.raises(lernen.Fehler, match="gibt/es/nicht.md"):
        lernen.anreichern(daten, quelle)


def test_doppelter_schluessel_wird_gemeldet(quelle):
    daten = _daten()
    daten["eintraege"].append(dict(daten["eintraege"][0]))
    with pytest.raises(lernen.Fehler, match="doppelt"):
        lernen.anreichern(daten, quelle)


def test_env_datei_lesen(tmp_path):
    datei = tmp_path / ".env"
    datei.write_text("# Kommentar\nLERN_API_TOKEN=abc\n\nLERN_URL = http://x \n")
    assert lernen.env_datei_lesen(datei) == {"LERN_API_TOKEN": "abc", "LERN_URL": "http://x"}
    assert lernen.env_datei_lesen(tmp_path / "fehlt") == {}


FAECHER = [
    {"slug": "leer", "name": "Leeres Fach", "gesamt": 0, "beherrscht": 0, "themen": []},
    {"slug": "cloud-computing", "name": "Cloud Computing", "gesamt": 5, "beherrscht": 1, "themen": [
        {"schluessel": "cloud-computing/topics/docker", "titel": "Docker", "aktiv": True, "gesamt": 5,
         "beherrscht": 1, "themen": [
            {"schluessel": "cloud-computing/topics/docker/01-grundlagen", "titel": "Grundlagen", "aktiv": True,
             "gesamt": 3, "beherrscht": 1, "themen": []},
            {"schluessel": "cloud-computing/topics/docker/06-docker-networking", "titel": "Docker Networking",
             "aktiv": True, "gesamt": 2, "beherrscht": 0, "themen": []},
            {"schluessel": "cloud-computing/topics/docker/07-aus", "titel": "Abgeschaltet", "aktiv": False,
             "gesamt": 0, "beherrscht": 0, "themen": []},
        ]},
    ]},
]


def test_bereiche_ohne_leere_und_deaktivierte():
    liste = lernen.bereiche(FAECHER)
    assert [(b["name"], b["tiefe"]) for b in liste] == [
        ("Cloud Computing", 0), ("Docker", 1), ("Grundlagen", 2), ("Docker Networking", 2)]
    assert liste[0]["thema"] is None and liste[1]["thema"] == "cloud-computing/topics/docker"


def test_bereich_finden():
    liste = lernen.bereiche(FAECHER)
    assert lernen.bereich_finden(liste, "3")["name"] == "Grundlagen"
    assert lernen.bereich_finden(liste, "cloud")["thema"] is None
    assert lernen.bereich_finden(liste, "networking")["name"] == "Docker Networking"
    assert lernen.bereich_finden(liste, "Grundlagen")["name"] == "Grundlagen"
    with pytest.raises(lernen.Fehler, match="Kein Fach"):
        lernen.bereich_finden(liste, "quantenphysik")


def test_blatt_dateien_nur_aus_dem_quell_repo(tmp_path, monkeypatch):
    quelle = tmp_path / "quelle"
    (quelle / "cc").mkdir(parents=True)
    (quelle / "cc" / "bild.png").write_bytes(b"x")
    (tmp_path / "geheim.png").write_bytes(b"x")
    sitzung = tmp_path / "sitzung"
    sitzung.mkdir()
    (sitzung / "blatt.pdf").write_bytes(b"%PDF")
    monkeypatch.setattr(lernen, "QUELLE", quelle)

    dateien = lernen.blatt_dateien(sitzung, {"dateien": [{"name": "bild-1.png", "quelle": "cc/bild.png"}]})
    assert [name for name, _ in dateien] == ["bild-1.png", "blatt.pdf"]
    with pytest.raises(lernen.Fehler, match="nicht im Quell-Repo"):
        lernen.blatt_dateien(sitzung, {"dateien": [{"name": "x.png", "quelle": "../geheim.png"}]})
    with pytest.raises(lernen.Fehler, match="nicht im Quell-Repo"):
        lernen.blatt_dateien(sitzung, {"dateien": [{"name": "x.png", "quelle": "cc/fehlt.png"}]})


def test_geaenderte_faecher():
    dateien = "M\tcc/topics/docker/TOPIC.md\nA\tse/origin-tasks/task-9/TASKS.md\nM\tREADME.md\nR100\tcc/a.md\tbwl/b.md\n"
    assert lernen.geaenderte_faecher(dateien) == ["bwl", "cc", "se"]
