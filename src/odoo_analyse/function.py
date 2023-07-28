# © 2023 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from typing import Union


class Function:
    def __init__(
        self, args: list, complexity: int = None, lines: int = None, halstead: int = 0
    ):
        self.args = args
        self.complexity = complexity or 0
        self.lines = lines or 0
        self.halstead = halstead or 0

    def __repr__(self) -> str:
        return f"<Function: {self.args}>"

    def to_json(self) -> dict:
        return {
            "args": self.args,
            "arg_count": len(self.args),
            "complexity": self.complexity,
            "lines": self.lines,
            "halstead": self.halstead,
        }

    @classmethod
    def from_json(cls, data: Union[dict, list]) -> "Function":
        if isinstance(data, (list, tuple)):
            return cls(data)
        return cls(
            data["args"],
            data.get("complexity"),
            data.get("lines"),
            data.get("halstead"),
        )
