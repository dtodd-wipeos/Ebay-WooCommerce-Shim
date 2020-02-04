#!/usr/bin/env python3

import os
import sys

from .db import Database

from woocommerce import API

class WooCommerceShim(Database):
    """
        Contains various methods for interacting with
        the WooCommerce API. These methods will do things
        such as adding new products, and removing sold
        products.

        TODO: Multi-threading.
    """

    def __init__(self, *args, **kwargs):
        super(WooCommerceShim, self).__init__(*args, **kwargs)

        self.api = API(
            url=os.environ.get('woo_url', False),
            consumer_key=os.environ.get('woo_key', False),
            consumer_secret=os.environ.get('woo_secret', False)
        )


