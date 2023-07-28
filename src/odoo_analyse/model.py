# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import ast
from statistics import median

from mccabe import PathGraphingAstVisitor
from radon.metrics import h_visit_ast

from .field import Field
from .function import Function
from .utils import geometric_mean, get_ast_source_segment


class Model:
    def __init__(self, name=None, inherit=None, inherits=None, fields=None, funcs=None):
        self.name = name
        self.inherit = set(inherit or [])
        self.inherits = inherits or {}
        self.fields = fields or {}
        self.funcs = funcs or {}

    @property
    def complexity(self) -> int:
        complexities = [f.complexity for f in self.funcs.values()]
        return median(complexities or [0])

    @property
    def max_complexity(self) -> int:
        return max((f.complexity for f in self.funcs.values()), default=0)

    @property
    def min_complexity(self) -> int:
        return min((f.complexity for f in self.funcs.values()), default=0)

    @property
    def halstead(self) -> int:
        return geometric_mean([f.halstead for f in self.funcs.values()])

    def is_model(self) -> bool:
        return bool(self.name or self.inherit)

    def __repr__(self) -> str:
        if self.is_model():
            return f"<Model: {self.name}>"
        return f"<Class: {self.name}>"

    def copy(self) -> "Model":
        return Model(
            self.name,
            self.inherit.copy(),
            self.inherits.copy(),
            self.fields.copy(),
            self.funcs.copy(),
        )

    def update(self, other: "Model") -> None:
        if self.name == other.name:
            self.inherit.update(other.inherit)
            self.inherits.update(other.inherits)
            self.fields.update(other.fields)
            self.funcs.update(other.funcs)

    def _parse_assign(self, obj: ast.Assign, content: str) -> None:
        assignments = [k.id for k in obj.targets if isinstance(k, ast.Name)]
        if len(assignments) != 1:
            return

        assign, value = assignments[0], obj.value
        if assign == "_name":
            if not isinstance(value, ast.Constant):
                return

            self.name = ast.literal_eval(value)
        elif assign == "_inherit":
            if isinstance(value, ast.Name) and value.id == "_name":
                self.inherit.add(self.name)
            elif not isinstance(value, ast.Name):
                value = ast.literal_eval(value)
                if isinstance(value, list):
                    self.inherit.update(value)
                else:
                    self.inherit.add(value)
        elif assign == "_inherits":
            inhs = ast.literal_eval(value)
            if isinstance(inhs, dict):
                self.inherits.update(inhs)
                self.fields.update({k: Field("fields.Many2one") for k in inhs.values()})
        elif isinstance(value, ast.Call):
            f = value.func
            if not isinstance(f, ast.Attribute) or not isinstance(f.value, ast.Name):
                return

            if f.value.id == "fields":
                definition = get_ast_source_segment(content, value)
                self.fields[assign] = Field(f"fields.{f.attr}", definition)

    def _parse_function(self, obj: ast.FunctionDef) -> None:
        visitor = PathGraphingAstVisitor()
        visitor.preorder(obj, visitor)

        halstead_visitor = h_visit_ast(obj)

        complexity = 0
        for graph in visitor.graphs.values():
            complexity = max(complexity, graph.complexity())

        self.funcs[obj.name] = Function(
            [a.arg for a in obj.args.args],
            complexity=complexity,
            lines=obj.end_lineno - obj.lineno,
            halstead=halstead_visitor.total.volume,
        )

    def to_json(self) -> dict:
        return {
            "name": self.name,
            "inherit": list(self.inherit),
            "inherits": self.inherits,
            "fields": {k: v.to_json() for k, v in self.fields.items()},
            "field_count": len(self.fields),
            "funcs": {k: v.to_json() for k, v in self.funcs.items()},
            "func_count": len(self.funcs),
            "complexity": self.complexity,
            "min_complexity": self.min_complexity,
            "max_complexity": self.max_complexity,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Model":
        return cls(
            name=data.get("name", None),
            inherit=data.get("inherit", None),
            inherits=data.get("inherits", None),
            fields={k: Field.from_json(v) for k, v in data.get("fields", {}).items()},
            funcs={k: Function.from_json(v) for k, v in data.get("funcs", {}).items()},
        )

    @classmethod
    def from_ast(cls, obj: ast.ClassDef, content: str) -> "Model":
        model = cls()
        for child in obj.body:
            if isinstance(child, ast.Assign):
                model._parse_assign(child, content)
            elif isinstance(child, ast.FunctionDef):
                model._parse_function(child)

        if model.inherit and not model.name:
            model.name = list(model.inherit)[0]

        return model
