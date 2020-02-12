#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import sys
import logging

# Log to console
LOG_HANDLER = logging.StreamHandler(sys.stdout)
LOG_FORMAT = logging.Formatter('%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s')
LOG_HANDLER.setFormatter(LOG_FORMAT)
