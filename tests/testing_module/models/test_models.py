from odoo import fields, models


class TestAbstract(models.AbstractModel):
    _name = "test.abstract"


class TestModel(models.Model):
    _name = "test.model"
    _inherits = {
        "user_id": "res.users",
    }

    a = fields.Char()
    b = fields.Text()
    c = fields.Integer()
    d, e = 1, 2


class ResUsers(models.Model):
    _inherit = ["res.users", "test.abstract"]

    new_boolean = fields.Boolean()
    new_m2o = fields.Many2one("res.partner")


class ResPartner(models.Model):
    _inherit = "res.partner"

    def testing(self, async):
        print(async)
        print(RPC)

    k = int()


class ResPartnerB(models.Model):
    _inherit = "res.partner"
