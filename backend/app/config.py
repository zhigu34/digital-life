import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    secure_cookie: bool = False
    trusted_origins: tuple[str, ...] = ()
    session_ttl: int = 14 * 24 * 60 * 60
    cookie_name: str = "digital_life_session"
    metadata_disabled: bool = False
    tmdb_api_key: str = ""

    @property
    def database_path(self) -> Path:
        return self.data_dir / "digital-life.db"

    @classmethod
    def from_env(cls, data_dir: str | Path | None = None) -> "Settings":
        default_data = Path(__file__).resolve().parents[2] / "data"
        path = Path(data_dir or os.getenv("DIGITAL_LIFE_DATA_DIR", str(default_data))).resolve()
        secure = os.getenv("DIGITAL_LIFE_SECURE_COOKIE", "false").lower()
        if secure not in {"true", "false", "1", "0"}:
            raise ValueError("DIGITAL_LIFE_SECURE_COOKIE must be true or false")
        disabled = os.getenv("DIGITAL_LIFE_DISABLE_METADATA", "false").lower()
        if disabled not in {"true", "false", "1", "0"}:
            raise ValueError("DIGITAL_LIFE_DISABLE_METADATA must be true or false")
        origins = tuple(
            x.strip().rstrip("/")
            for x in os.getenv("DIGITAL_LIFE_TRUSTED_ORIGINS", "").split(",")
            if x.strip()
        )
        return cls(
            path,
            secure in {"true", "1"},
            origins,
            metadata_disabled=disabled in {"true", "1"},
            tmdb_api_key=os.getenv("DIGITAL_LIFE_TMDB_API_KEY", "").strip(),
        )
