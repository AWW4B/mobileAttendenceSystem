"""Shared configuration for the portal and the MEC server."""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

DEFAULT_DATA_DIR = Path(__file__).resolve().parents[1] / "data"

# Must match models/model_contract.json and the Android app.
EMBEDDING_DIM = 512

PORTAL_ISSUER = "attend-portal"   # login tokens and section grants
MEC_ISSUER = "attend-mec"         # attendance receipts


@dataclass(frozen=True)
class Settings:
    data_dir: Path
    access_token_ttl_s: int = 3600      # teacher login token
    grant_ttl_s: int = 900              # one-time "open a session for this section" grant
    session_ttl_s: int = 600            # how long a capture session stays open on the MEC
    receipt_ttl_s: int = 7 * 24 * 3600  # phone may hold a receipt offline this long
    request_clock_skew_s: int = 120     # tolerated skew for signed device requests
    max_metrics_bytes: int = 8192       # cap on research metrics attached to a submission

    @property
    def portal_dir(self) -> Path:
        return self.data_dir / "portal"

    @property
    def mec_dir(self) -> Path:
        return self.data_dir / "mec"

    @property
    def shared_dir(self) -> Path:
        """Only public keys and the dev admin token live here."""
        return self.data_dir / "shared"

    @classmethod
    def from_env(cls) -> "Settings":
        return cls(data_dir=Path(os.environ.get("ATTEND_DATA_DIR", DEFAULT_DATA_DIR)))
