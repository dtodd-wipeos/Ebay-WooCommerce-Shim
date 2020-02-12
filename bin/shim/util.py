#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

"""
    This file contains constants and utility methods
    that are used all over the place

    For now, the only constant we need is LOG_HANDLER
"""

import sys
import logging

# Log to console
LOG_HANDLER = logging.StreamHandler(sys.stdout)
LOG_FORMAT = logging.Formatter('%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s')
LOG_HANDLER.setFormatter(LOG_FORMAT)
