# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~# Aetheris V5 #~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#
# Copyright (C) 2026 Aetheris Intelligence Project
# Licensed under the GNU Affero General Public License v3.0
# ~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~~#

import pytest
from userbot.sql_helper.globals import addgvar, delgvar, gvarstatus


def test_storage_caching_and_invalidation():
    test_key = "v5_test_feature_flag"
    test_val = "enabled_v5_mode"

    # Set value
    addgvar(test_key, test_val)

    # First fetch (populated cache)
    val1 = gvarstatus(test_key)
    assert val1 == test_val

    # Second fetch (cache hit)
    val2 = gvarstatus(test_key)
    assert val2 == test_val

    # Update value
    new_val = "updated_v5_mode"
    addgvar(test_key, new_val)
    val3 = gvarstatus(test_key)
    assert val3 == new_val

    # Delete value (cache invalidated)
    delgvar(test_key)
    val4 = gvarstatus(test_key)
    assert val4 is None
