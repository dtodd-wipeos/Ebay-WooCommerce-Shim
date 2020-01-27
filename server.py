#!/usr/bin/env python3

from pprint import pprint
from optparse import OptionParser
from shim.API import APIShim

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

    shim = APIShim()
    shim.set_date_range(start_date='2020-01-01', days=1).set_range_filter()

    shim.try_command('get_seller_list')

    outfile = open('items.py', 'w')
    pprint(shim.got_items, outfile)
