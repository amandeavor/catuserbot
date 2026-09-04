# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris UserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from .extdl import *
from .flags import *
from .paste import *

flag = True
check = 0
while flag:
    try:
        from . import format as _format
        from . import utils as _catutils
        from .events import *
        from .flags import *
        from .format import *
        from .utils import *

        break
    except ModuleNotFoundError as e:
        install_pip(e.name)
        check += 1
        if check > 5:
            break
