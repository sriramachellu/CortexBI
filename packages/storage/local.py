import os
from pathlib import Path


class LocalDiskStore:
    def __init__(self, root: str = "./var/storage"):
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    def _path(self, key: str) -> Path:
        safe_key = key.lstrip("/")
        full = (self._root / safe_key).resolve()
        if not str(full).startswith(str(self._root.resolve())):
            raise ValueError(f"Invalid key: {key}")
        return full

    def put(self, key: str, data: bytes) -> str:
        p = self._path(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_bytes(data)
        return key

    def get(self, key: str) -> bytes:
        p = self._path(key)
        if not p.exists():
            raise FileNotFoundError(f"Object not found: {key}")
        return p.read_bytes()

    def exists(self, key: str) -> bool:
        return self._path(key).exists()

    def delete(self, key: str) -> None:
        p = self._path(key)
        if p.exists():
            os.remove(p)

    def url(self, key: str) -> str:
        return f"local://{key}"
