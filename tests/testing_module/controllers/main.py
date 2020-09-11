# © 2020 initOS GmbH
# License LGPL-3.0 or later (https://www.gnu.org/licenses/lgpl.html)

import odoo.addons.base.controllers.rpc as rpc
from odoo.addons.base.controllers.rpc import RPC


class TestRPC(RPC):
    print(rpc)
