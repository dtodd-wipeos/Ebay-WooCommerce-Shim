#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import logging

from .db import Database

from woocommerce import API as WCAPI
from wordpress import API as WPAPI

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

        # Setup logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        log_handler = logging.StreamHandler(sys.stdout)
        log_format = logging.Formatter('%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(log_format)
        self.log.addHandler(log_handler)

        self.api = WCAPI(
            url=os.environ.get('woo_url', False),
            consumer_key=os.environ.get('woo_key', False),
            consumer_secret=os.environ.get('woo_secret', False)
        )

        self.wp_api = WPAPI(
            url=os.environ.get('woo_url', False),
            api='wp-json',
            version='wp/v2',
            wp_user=os.environ.get('wordpress_user', False),
            wp_pass=os.environ.get('wordpress_app_password', False),
            basic_auth=True,
            user_auth=True,
            consumer_key=False,
            consumer_secret=False
        )

    def __does_image_exist(self, slug):
        """
            Searches the Wordpress media library for
            any files that have a URL `slug` that
            matches the one provided

            Returns True if the file exists, and False otherwise
        """

        self.log.debug('Checking if a file has a slug matching: %s' % (slug))
        result = self.wp_api.get('/media?slug=%s' % (slug)).json()

        if len(result) == 0:
            return False
        return True

    def upload_image(self, image, post_id):
        """
            Uploads the provided `image` to wordpress, and returns the response

            `image` is a dictionary containing the following keys:

            `name` - This is the destination file name, including extension

            `type` - This is the MIMETYPE of the image, usually derived from the extension

            `data` - This is a bytes-like object representing the entire image. We get this
            from dowloading an image directly from Ebay's servers and temporarily storing it
            in memory

            `post_id` is the post in which to attach the image to. This is returned in the
            response from `self.create_product()`
        """

        # Don't upload a duplicate image if it was uploaded in the past
        if self.__does_image_exist(image.get('slug', '')):
            self.log.warning(
                "Image %s already exists on wordpress. Not uploading again" % (image.get('name'))
            )
            return None

        self.log.info("Uploading %s to wordpress" % (image.get('name')))

        endpoint = '/media?post=%d' % (post_id)

        headers = {
            'cache-control': 'no-cache',
            'content-disposition': 'attachment; filename=%s' % (image.get('name', '')),
            'content-type': '%s' % (image.get('type', ''))
        }

        return self.wp_api.post(endpoint, image.get('data'), headers=headers)
