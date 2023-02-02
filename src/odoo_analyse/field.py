# © 2023 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)


class Field:
    def __init__(self, ttype: str, definition: str = None):
        self.ttype = ttype
        self.definition = definition

    def __repr__(self) -> str:
        return f"<Field: {self.ttype}>"

    def to_json(self) -> dict:
        return {
            "ttype": self.ttype,
            "definition": self.definition,
        }

    @classmethod
    def from_json(cls, data: dict) -> "Field":
        return Field(data["ttype"], data.get("definition"))
