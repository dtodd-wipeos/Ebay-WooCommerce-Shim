#!/usr/bin/env python3

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
    shim.set_date_range(start_date='2019-01-01').set_range_filter()

    shim.try_command('get_items')
