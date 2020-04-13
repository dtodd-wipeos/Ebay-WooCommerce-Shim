#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import logging

from shim.ebay import EbayShim
from shim.woo import WooCommerceShim
from shim.util import LOG_HANDLER

class Server:
    """
        Provides a framework for sequentially running the shim commands
    """

    def __init__(self):
        """
            Sets up internals, such as logging and the API Shims
        """
        # Set up logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        self.log.addHandler(LOG_HANDLER)

        # Shims
        self.ebay = EbayShim()
        self.woo = WooCommerceShim()

        self.active_item_ids = self.woo.db_get_active_item_ids()
        self.inactive_item_ids = self.woo.db_get_inactive_uploaded_item_ids()

    def __ebay_download_products(self):
        """
            Sets up a date filter to get all items that will
            be automatically ended at the end of the range and
            gets the products from that
        """
        self.log.info('Setting date range filter to today and ending at 35 days in the future')
        self.ebay.set_date_range(start_date='', days=35, range_type='End').set_range_filter()
        self.ebay.try_command('get_seller_list')

    def __ebay_download_metadata(self):
        """
            Once we have gotten all of the items above,
            we can get the ItemSpecifics and Description fields
        """
        # Disable downloading metadata due to the need to map attributes
        # And I hit the time constraints to get this launched
        # self.ebay.try_command('get_item_metadata')
        pass

    def __woo_upload_products(self):
        """
            Gets all of the active item ids and creates a
            product on WooCommerce that matches its data
        """

        for item_id in self.active_item_ids:
            self.woo.try_command('create_product', item_id)

    def __woo_upload_metadata(self):
        """
            Once the products have been uploaded, we will
            have the post ids for each product, which is
            required to upload any images or other attributes
        """

        for item_id in self.active_item_ids:
            self.woo.try_command('set_featured_image', item_id)
            # Disable uploading images due to duplication bug. We have
            # a wordpress plugin that handles the image downloading
            # self.woo.try_command('upload_images', item_id)
            # Disable uploading attributes due to the need to map them
            # And I hit the time constraints to get this launched
            # self.woo.try_command('upload_attributes', item_id)

    def __woo_delete_products(self):
        """
            Deletes any uploaded products that have either
            been marked as Complete, or have reached their
            end_date
        """
        for item_id in self.inactive_item_ids:
            self.woo.try_command('delete_product', item_id)

    def start(self):
        """
            Called to start everything.

            This will do the following in order:
            1. Download products from ebay with GetSellerList
            2. Download product ItemSpecifics with GetItem
            3. Upload the downloaded products to WooCommerce
            4. Upload the downloaded product metadata to WooCommerce
            5. Delete any products that ended on ebay from WooCommerce
        """
        # self.__ebay_download_products()
        # self.__ebay_download_metadata()
        # self.__woo_upload_products()
        self.__woo_upload_metadata()
        # self.__woo_delete_products()

if __name__ == '__main__':
    Server().start()
