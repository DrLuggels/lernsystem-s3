import os
from dataclasses import dataclass


@dataclass(frozen=True)
class Settings:
    db_pfad: str
    api_token: str
    passwort: str
    secret: str
    cookie_secure: bool = True

    @classmethod
    def aus_env(cls) -> "Settings":
        fehlend = [n for n in ("LERN_API_TOKEN", "LERN_PASSWORT", "LERN_SECRET") if not os.environ.get(n)]
        if fehlend:
            raise RuntimeError("Umgebungsvariablen fehlen: " + ", ".join(fehlend))
        return cls(
            db_pfad=os.environ.get("LERN_DB", "/data/lernsystem.db"),
            api_token=os.environ["LERN_API_TOKEN"],
            passwort=os.environ["LERN_PASSWORT"],
            secret=os.environ["LERN_SECRET"],
            cookie_secure=os.environ.get("LERN_COOKIE_SECURE", "1") != "0",
        )
