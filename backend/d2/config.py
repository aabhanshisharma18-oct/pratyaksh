from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class D2Config:
    root: Path
    database: Path
    originals: Path
    derivatives: Path
    exports: Path
    demo_identity: str
    max_upload_bytes: int = 250 * 1024 * 1024

    @classmethod
    def from_env(cls) -> "D2Config":
        root = Path(os.getenv("PRATYAKSH_D2_ROOT", Path(__file__).parents[1] / "data" / "d2")).resolve()
        return cls(root, Path(os.getenv("PRATYAKSH_D2_DB", root / "d2.sqlite3")).resolve(),
                   root / "originals", root / "derivatives", root / "exports",
                   os.getenv("PRATYAKSH_DEMO_IDENTITY", "Demo examiner (self-declared)"))

    def ensure(self) -> None:
        for path in (self.root, self.originals, self.derivatives, self.exports):
            path.mkdir(parents=True, exist_ok=True)
