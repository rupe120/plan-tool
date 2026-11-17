from dataclasses import dataclass
from datetime import date


@dataclass
class Task:
    id: int
    title: str
    done: bool = False
    due: date | None = None
