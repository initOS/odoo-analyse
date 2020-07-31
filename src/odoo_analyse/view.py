# © 2020 initOS GmbH
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

import logging

_logger = logging.getLogger(__name__)


class View:
    def __init__(self, name=None, inherit=None, calls=None, model=None):
        self.name = name
        self.inherit = inherit
        self.calls = set(calls or [])
        self.model = model

    def __repr__(self):
        return "<View: %s>" % self.name

    def copy(self):
        return View(self.name, self.inherit, self.calls.copy(), self.model)

    def update(self, other):
        if self.name == other.name:
            self.calls.update(other.calls)

    @staticmethod
    def enforce_fullname(name, module_name):
        if not isinstance(name, str):
            return None
        if "." in name:
            return name
        return "%s.%s" % (module_name, name)

    def to_json(self):
        return {
            "name": self.name,
            "inherit": self.inherit,
            "model": self.model,
            "calls": list(self.calls),
        }

    @classmethod
    def from_json(cls, data):
        return cls(
            name=data.get("name", None),
            inherit=data.get("inherit", None),
            model=data.get("model", None),
            calls=data.get("calls", None),
        )

    @classmethod
    def from_xml(cls, module_name, obj):
        name = obj.attrib.get("id", None)

        if obj.tag == "template":
            inherit = obj.attrib.get("inherit_id", None)
            calls = obj.xpath(".//@t-call")
            model = None
        elif obj.tag == "record" and obj.attrib.get("model") == "ir.ui.view":
            tmp = obj.xpath('./field[@name="inherit_id"]/@ref')
            inherit = tmp[0] if tmp else None
            calls = obj.xpath('./field[@name="arch"]//@t-call')
            model = obj.xpath('./field[@name="model"]//text()')
            model = model[0] if model else None
        else:
            return None

        calls = {View.enforce_fullname(c, module_name) for c in calls}
        name = View.enforce_fullname(name, module_name)

        if name:
            return cls(name, inherit, calls, model)
        if isinstance(inherit, str):
            name = "%s.%s" % (module_name, inherit.rsplit(".")[-1])
            return cls(name, inherit, calls, model)
        return None
