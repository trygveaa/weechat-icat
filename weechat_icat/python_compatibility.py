from __future__ import annotations


# Copied from https://peps.python.org/pep-0616/ for support for Python < 3.9
def removeprefix(self: str, prefix: str) -> str:
    if self.startswith(prefix):
        return self[len(prefix) :]
    else:
        return self[:]


# Copied from https://peps.python.org/pep-0616/ for support for Python < 3.9
def removesuffix(self: str, suffix: str) -> str:
    if suffix and self.endswith(suffix):
        return self[: -len(suffix)]
    else:
        return self[:]
