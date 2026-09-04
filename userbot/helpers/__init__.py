# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# CatUserBot #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2020-2023 by TgCatUB@Github.

# This file is part of: https://github.com/TgCatUB/catuserbot
# and is released under the "GNU v3.0 License Agreement".

# Please see: https://github.com/TgCatUB/catuserbot/blob/master/LICENSE
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

from . import fonts
from . import memeshelper as catmemes
from .aiohttp_helper import AioHttp
from .utils import *

flag = True
_retry_count = 0
while flag:
    try:
        from .chatbot import *
        from .functions import *
        from .memeifyhelpers import *
        from .progress import *
        from .qhelper import *
        from .tools import *
        from .utils import _catutils, _format

        break
    except (ModuleNotFoundError, ImportError) as e:
        pkg = getattr(e, "name", None)
        if pkg:
            install_pip(pkg)
        _retry_count += 1
        if _retry_count > 5:
            break
