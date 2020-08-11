#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

class Image:

    """
        Contains a picture that will get uploaded
    """

    def __init__(self, name, slug, ebay_url, mime_type, data):
        self.name = name
        self.slug = slug
        self.ebay_url = ebay_url
        self.mime_type = mime_type
        self.data = data
