#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

class Image:

    """
        Contains a picture that will get uploaded
    """

    def __init__(self, *args, **kwargs):
        super(Image, self).__init__(*args, **kwargs)

        self.name = kwargs.get('name')
        self.slug = kwargs.get('slug')
        self.ebay_url = kwargs.get('ebay_url')
        self.mime_type = kwargs.get('mime_type')
        self.data = kwargs.get('data')
