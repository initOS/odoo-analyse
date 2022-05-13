# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

from odoo import fields, models


class TestAbstract(models.AbstractModel):
    _name = "test.abstract"


class TestModel(models.Model):
    _name = "test.model"
    _inherits = {
        "res.users": "user_id",
    }

    a = fields.Char()
    b = fields.Text()
    c = fields.Integer()
    d, e = 1, 2


class ResUsers(models.Model):
    _inherit = ["res.users", "test.abstract"]

    def _get_default(self):
        return False

    new_boolean = fields.Boolean()
    new_m2o = fields.Many2one(
        "res.partner",
        _get_default(),
        string="Label",
        default=_get_default + 1,
    )


class ResPartner(models.Model):
    _inherit = "res.partner"

    def testing(self, async, k=100):
        print(async)
        print(RPC, k)

    k = int()


class ResPartnerB(models.Model):
    _inherit = "res.partner"
