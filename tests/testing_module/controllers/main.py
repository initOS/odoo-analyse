# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)
# disable: pylint

from odoo.addons.base.controllers import rpc


class TestRPC(rpc.RPC):
    print(rpc)
