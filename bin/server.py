#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

from pprint import pprint
from optparse import OptionParser
from shim.ebay import EbayShim
from shim.woo import WooCommerceShim

def parse_options():
    parser = OptionParser(usage="Usage: %prog [options]")

    parser.add_option(
        "-d",
        action='store_true',
        dest='debug', 
        default=False,
        help='Enable API Debugging [default: %default]')

    (opts, args) = parser.parse_args()
    return opts, args


if __name__ == '__main__':
    # Currently unused
    (opts, args) = parse_options()

    ebay_shim = EbayShim()
    woo_shim = WooCommerceShim()

    print('it works!')

    # Store all items that started within this date range
    # ebay_shim.set_date_range(start_date='2020-02-01', days=1).set_range_filter()
    # # This will also store metadata for items that are still active
    # ebay_shim.try_command('get_seller_list')
