#!/usr/bin/env python3

import os
import sys

from .db import Database

class WooCommerce(Database):
    """
        Contains various methods for interacting with
        the WooCommerce API. These methods will do things
        such as adding new products, and removing sold
        products.

        TODO: Multi-threading.
    """

    def __init__(self, *args, **kwargs):
        super(WooCommerce, self).__init__(*args, **kwargs)


