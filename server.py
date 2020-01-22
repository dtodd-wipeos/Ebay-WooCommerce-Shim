#!/usr/bin/env python3

import os
from optparse import OptionParser

from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError

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
    (opts, args) = parse_options()

    shim = APIShim()
    shim.set_date_range(start_date='2019-01-01').set_range_filter()

    print(shim.date_range)
    print(shim.seller_list)

    try:
        api = Trading(
            domain=os.environ.get('ebay_domain', False),
            # compatibility=int(os.environ.get('ebay_api_version', 648)),
            appid=os.environ.get('ebay_appid', False),
            certid=os.environ.get('ebay_certid', False),
            devid=os.environ.get('ebay_devid', False),
            token=os.environ.get('ebay_token', False),
            config_file=None,
            debug=opts.debug
        )

        items = api.execute('GetSellerEvents', shim.seller_list).dict().get('ItemArray', None)
        print(items)

    except ConnectionError as e:
        print(e)
        print(e.response.dict())
