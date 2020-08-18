# © 2020 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import ast

from .utils import get_ast_source_segment


class Field:
    def __init__(self, ttype, definition=None):
        self.ttype = ttype
        self.definition = definition

    def __repr__(self):
        return "<Field: %s>" % self.ttype

    def to_json(self):
        return {
            "ttype": self.ttype,
            "definition": self.definition,
        }

    @classmethod
    def from_json(cls, data):
        return Field(data["ttype"], data.get("definition"))


class Model:
    def __init__(self, name=None, inherit=None, inherits=None, fields=None, funcs=None):
        self.name = name
        self.inherit = set(inherit or [])
        self.inherits = inherits or {}
        self.fields = fields or {}
        self.funcs = funcs or {}

    def __repr__(self):
        return "<Model: %s>" % self.name

    def copy(self):
        return Model(
            self.name,
            self.inherit.copy(),
            self.inherits.copy(),
            self.fields.copy(),
            self.funcs.copy(),
        )

    def update(self, other):
        if self.name == other.name:
            self.inherit.update(other.inherit)
            self.inherits.update(other.inherits)
            self.fields.update(other.fields)
            self.funcs.update(other.funcs)

    def _parse_assign(self, obj, content):
        assignments = [k.id for k in obj.targets if isinstance(k, ast.Name)]
        if len(assignments) != 1:
            return

        assign, value = assignments[0], obj.value
        if assign == "_name":
            self.name = ast.literal_eval(value)
        elif assign == "_inherit":
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
                self.fields[assign] = Field("fields.%s" % f.attr, definition)

    def to_json(self):
        return {
            "name": self.name,
            "inherit": list(self.inherit),
            "inherits": self.inherits,
            "fields": {k: v.to_json() for k, v in self.fields.items()},
            "funcs": self.funcs,
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            name=data.get("name", None),
            inherit=data.get("inherit", None),
            inherits=data.get("inherits", None),
            fields={k: Field.from_json(v) for k, v in data.get("fields", {}).items()},
            funcs=data.get("funcs", None),
        )

    @classmethod
    def from_ast(cls, obj, content):
        model = cls()
        for child in obj.body:
            if isinstance(child, ast.Assign):
                model._parse_assign(child, content)
            elif isinstance(child, ast.FunctionDef):
                model.funcs[child.name] = [a.arg for a in child.args.args]

        if model.name:
            return model
        if len(model.inherit) == 1:
            model.name = list(model.inherit)[0]
            return model
        return None
