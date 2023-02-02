# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import logging
from typing import List

from lxml import etree

_logger = logging.getLogger(__name__)


TopLevelTags = [
    "act_window",
    "assert",
    "delete",
    "function",
    "menuitem",
    "record",
    "report",
    "template",
    "url",
]


class Record:
    def __init__(
        self,
        name: str = None,
        inherit: str = None,
        calls: List[str] = None,
        model: str = None,
        complexity: int = None,
        lines: int = None,
        view: bool = False,
    ):
        self.name = name
        self.inherit = inherit
        self.calls = set(calls or [])
        self.model = model
        self.complexity = complexity or 0
        self.lines = lines or 0
        self.view = view

    def __repr__(self) -> str:
        if self.view:
            return f"<View: {self.name}>"
        return f"<Data: {self.name}>"

    def is_view(self) -> bool:
        return bool(self.view)

    def copy(self) -> "Record":
        return Record(
            self.name,
            self.inherit,
            self.calls.copy(),
            self.model,
            self.complexity,
            self.lines,
            self.view,
        )

    def update(self, other: "Record") -> None:
        if self.name == other.name:
            self.calls.update(other.calls)
            self.complexity += other.complexity
            self.lines += other.lines

    @staticmethod
    def enforce_fullname(name: str, module_name: str) -> str:
        if not isinstance(name, str):
            return None
        if "." in name:
            return name
        return f"{module_name}.{name}"

    @classmethod
    def _calculate_complexity(cls, obj: etree.Element) -> int:
        return len(obj.xpath(".//* | .//@*"))

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "inherit": self.inherit,
            "model": self.model,
            "calls": list(self.calls),
            "view": self.view,
            "complexity": self.complexity,
            "lines": self.lines,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Record":
        return cls(
            name=data.get("name", None),
            inherit=data.get("inherit", None),
            model=data.get("model", None),
            calls=data.get("calls", None),
            complexity=data.get("complexity", None),
            lines=data.get("lines", 0),
            view=data.get("view", True),
        )

    @classmethod
    def from_xml(cls, module_name: str, obj: etree.Element) -> "Record":
        name = obj.attrib.get("id", None)

        view = False
        if obj.tag == "template":
            inherit = obj.attrib.get("inherit_id", None)
            calls = obj.xpath(".//@t-call")
            model = None
            view = True
        elif obj.tag == "record" and obj.attrib.get("model") == "ir.ui.view":
            tmp = obj.xpath('./field[@name="inherit_id"]/@ref')
            inherit = tmp[0] if tmp else None
            calls = obj.xpath('./field[@name="arch"]//@t-call')
            model = obj.xpath('./field[@name="model"]//text()')
            model = model[0] if model else None
            view = True
        elif obj.tag == "record":
            model = obj.attrib.get("model")
            calls = []
            inherit = None
        else:
            return None

        calls = {Record.enforce_fullname(c, module_name) for c in calls}
        name = Record.enforce_fullname(name, module_name)
        lines = len(etree.tostring(obj, pretty_print=True).splitlines())
        complexity = cls._calculate_complexity(obj)

        if name:
            return cls(name, inherit, calls, model, complexity, lines, view)

        if isinstance(inherit, str):
            name = f"{module_name}.{inherit.rsplit('.')[-1]}"
            return cls(name, inherit, calls, model, complexity, lines, view)

        return None


class View(Record):
    def __init__(
        self,
        name: str = None,
        inherit: str = None,
        calls: List[str] = None,
        model: str = None,
        complexity: int = None,
        lines: int = None,
    ):
        super().__init__(
            name=name,
            inherit=inherit,
            calls=calls,
            model=model,
            complexity=complexity,
            lines=lines,
            view=True,
        )
