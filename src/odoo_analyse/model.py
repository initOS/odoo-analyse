# © 2020 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import ast


class Model:
    def __init__(self, name=None, inherit=None, inherits=None, fields=None):
        self.name = name
        self.inherit = set(inherit or [])
        self.inherits = inherits or {}
        self.fields = fields or {}

    def __repr__(self):
        return "<Model: %s>" % self.name

    def copy(self):
        return Model(
            self.name, self.inherit.copy(), self.inherits.copy(), self.fields.copy(),
        )

    def update(self, other):
        if self.name == other.name:
            self.inherit.update(other.inherit)
            self.inherits.update(other.inherits)
            self.fields.update(other.fields)

    def _parse_assign(self, obj):
        assignments = [k.id for k in obj.targets if isinstance(k, ast.Name)]
        if len(assignments) != 1:
            return

        assign, value = assignments[0], obj.value
        try:
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
                    self.fields.update({k: "fields.Many2one" for k in inhs})
            elif isinstance(value, ast.Call):
                f = value.func
                if not isinstance(f, ast.Attribute):
                    return

                if f.value.id == "fields":
                    self.fields[assign] = "fields.%s" % f.attr

        except Exception:
            pass

    def to_json(self):
        return {
            "name": self.name,
            "inherit": list(self.inherit),
            "inherits": self.inherits,
            "fields": self.fields,
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            name=data.get("name", None),
            inherit=data.get("inherit", None),
            inherits=data.get("inherits", None),
            fields=data.get("fields", None),
        )

    @classmethod
    def from_ast(cls, obj):
        model = cls()
        for child in obj.body:
            if isinstance(child, ast.Assign):
                model._parse_assign(child)

        if model.name:
            return model
        if len(model.inherit) == 1:
            model.name = list(model.inherit)[0]
            return model
        return None
