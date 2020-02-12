#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import logging

from shim.ebay import EbayShim
from shim.queue import ProductUploadQueue

if __name__ == '__main__':

    # Log to console
    log_handler = logging.StreamHandler(sys.stdout)
    log_format = logging.Formatter('%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(log_format)

    # Set up logging
    log = logging.getLogger(__name__)
    log.setLevel(os.environ.get('log_level', 'INFO'))
    log.addHandler(log_handler)

    # Ebay item ids to upload
    item_ids = [
        124070714664,
        124070794985,
        124070817266,
        124070858085,
        124070890853,
        124070906964,
        124071012427,
        124071844408,
        124071902830,
        124071918986,
        124071920856,
        124071965067,
        124071967215,
        124072021509,
        124072049703,
    ]

    ProductUploadQueue(item_ids).start()

    # Store all items that started within this date range
    # ebay_shim.set_date_range(start_date='2020-02-01', days=1).set_range_filter()
    # This will also store metadata for items that are still active
    # ebay_shim.try_command('get_seller_list')
