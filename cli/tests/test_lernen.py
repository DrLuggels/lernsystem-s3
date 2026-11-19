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
