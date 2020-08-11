#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import json
import time
import logging
import requests

from socket import timeout
from urllib3.exceptions import ReadTimeoutError

from .db import Database
from .util import LOG_HANDLER
from .image import Image

from woocommerce import API as WCAPI
from wordpress import API as WPAPI

DEFAULT_DESCRIPTION = """
<strong style="align-text:center;font-size:21px;">Request the price</strong>
[wpforms id="5280"]
"""

class WooCommerceShim(Database):
    """
        Contains various methods for interacting with
        the WooCommerce API. These methods will do things
        such as adding new products, and removing sold
        products.
    """

    def __init__(self, *args, **kwargs):
        super(WooCommerceShim, self).__init__(*args, **kwargs)

        # Setup logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        self.log.addHandler(LOG_HANDLER)

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

        mapping_path = os.environ.get('category_mapping',
                                      'database/ebay-to-woo-commerce-category-map.json')
        try:
            with open(mapping_path, 'r') as mapping_file:
                self.category_mapping = json.load(mapping_file)
        except IOError:
            self.category_mapping = None

    def __does_image_exist_on_woocommerce(self, slug):
        """
            Searches the Wordpress media library for
            any files that have a URL `slug` that
            matches the one provided

            Returns True if the file exists, and False otherwise

            This method is unreliable! Duplicates are basically guarenteed to happen...
        """

        self.log.info('Checking if a file has a slug matching: %s' % (slug))
        result = self.wp_api.get('/media?slug=%s' % (slug)).json()

        if len(result) == 0:
            return False
        return True

    def __divide_into_chunks(self, iterable, chunk_size=100):
        """
            Used to make bulk requests via the API, which limits
            the amount of products to change at once to 100

            `iterable` is something that can be iterated over, be
            it a list or a range. When a range, you must wrap the
            output of this method in `list()`

            `chunk_size` is optional, and defines how many products
            to change per request. The default of 100 is the maximum
            that the API will allow

            Returns the `iterable` containing as many items as are
            in the `chunk_size`
        """
        for i in range(0, len(iterable), chunk_size):
            yield iterable[i:i + chunk_size]

    def __search_map(self, value, field):
        """
            Uses List Comprehension to search for the `value` in the `field`.

            Normal usage would be similar to `self.__search_map(ebay_category_id, 'ebay_ids')`

            Returns an integer, which is the first matching Woo Commerce ID for
            the selected `value` (in the case that one ebay category is mapped to
            multiple woo commerce categories)

            When a matching category can't be found, this method will call itself
            to search for the "Uncategorized" `value` on the "wc-name" `field`
        """
        try:
            mapped = [key for key in self.category_mapping if value in key[field]]
            return int(mapped[0]['wc-id'])
        except IndexError: # Couldn't find it, return the uncategorized id
            return self.__search_map('Uncategorized', 'wc-name')

    def does_product_exist(self, item_id):
        """
            Determines if the product with the `item_id` has
            already been uploaded to WooCommerce, by checking
            for the truthyness of `post_id`
        """
        data = self.db_get_product_data(item_id)
        if data.get('post_id') is not None:
            return True
        return False

    def get_mapped_category_id(self, ebay_category_id):
        """
            Determines if the user provided a category mapping, and if so
            returns an integer, which is the Woo Commerce category id that
            is mapped to the `ebay_category_id` (or the Uncategorized category
            id if a mapping can not be found)

            In the case that the user has not provided a category mapping,
            this method returns None
        """
        if self.category_mapping is not None:
            return self.__search_map(ebay_category_id, 'ebay_ids')
        return None

    def download_product_images_from_ebay(self, item_id):
        """
            Downloads all of the images for a provided `item_id` and
            returns a dictionary containing the image name, mime type, and
            bytes-like object for the raw images

            The image URLs come from the database table `item_metadata`,
            which is populated when `self.__get_item_metadata()` runs
        """

        count = 0
        return_images = list()

        image_urls = self.db_get_product_image_urls(item_id)
        image_urls_count = len(image_urls)

        if image_urls_count > 0:
            self.log.info("Found %d image URLs for: %s" % (image_urls_count, item_id))

            for image in image_urls:
                url = image.get('value', '')

                if image.get('post_id') is not None:
                    self.log.warning("We've already uploaded %s, skipping download" % (url))
                    continue

                self.log.info("Downloading %s" % (url))
                req = requests.get(url)

                if req.content:
                    mime_type = req.headers.get('Content-Type', '')
                    slug = '%s-%d' % (item_id, count)
                    extension = mime_type.split('/')[1]
                    filename = '%s.%s' % (slug, extension)

                    if 'image' not in mime_type:
                        msg = "%d didn't get an image somehow. Content type was: %s"
                        self.log.error(msg % (item_id, mime_type))
                        continue

                    return_images.append(Image(
                        slug = slug,
                        ebay_url = url,
                        name = filename,
                        mime_type = mime_type,
                        data = req.content
                    ))

                    # self.log.info("Image %s downloaded" % (filename))

                    if count < image_urls_count:
                        self.log.debug("Waiting a quarter second until next download")
                        time.sleep(0.25)
                else:
                    self.log.error(
                        "No content returned. Is %s reachable in a browser?" % (url)
                    )

                count += 1
        else:
            self.log.warning("No Image URLs found for item: %s" % (item_id))

        return return_images

    def upload_image_to_woocommerce(self, image, post_id):
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

            Returns either a string containing the URL the image can be found at, or False
            if the image fails to be uploaded
        """

        self.log.info("Uploading %s to wordpress" % (image.name))

        endpoint = '/media?post=%d' % (post_id)

        headers = {
            'cache-control': 'no-cache',
            'content-disposition': 'attachment; filename=%s' % (image.name),
            'content-type': '%s' % (image.mime_type)
        }

        # Don't upload a duplicate image if it was uploaded in the past
        if self.__does_image_exist_on_woocommerce(image.slug):
            self.log.warning(
                "Image %s already exists on wordpress. Not uploading again" % (image.name)
            )
            return None, None

        # Upload the image
        response = self.wp_api.post(endpoint, image.data, headers=headers)

        try:
            image_id = response.json().get('id')
            url = response.json().get('guid', dict).get('raw')
            self.log.debug("Uploaded %s to %s" % (image.name, url))
            return image_id, url
        except AttributeError:
            self.log.error('Could not upload %s' % image.name)
            return None, None

    def upload_product_images(self, item_id):
        """
            With the provided `item_id`, the database
            is searched for the post id (set during
            `create_product`)

            When the post_id is found, it will be used
            to download the images for that product
            from ebay, and then upload the images
        """
        post_id = self.db_woo_get_post_id(item_id)
        gallery = []

        if post_id is not None:
            for image in self.download_product_images_from_ebay(item_id):
                image_id, url = self.upload_image_to_woocommerce(image, post_id)
                if image_id and url:
                    self.db_metadata_uploaded(image_id, item_id)
                    gallery.append({'id': image_id})

            # Add the images to the gallery
            self.api.put('products/%d' % (post_id), {'images': gallery}).json()
        else:
            self.log.warning('The product %d has not yet been uploaded' % (item_id))

        return self

    def create_product(self, item_id):
        """
            Pulls the product related to the `item_id`
            out of the database and uploads it to WooCommerce

            Returns the result as JSON
        """
        self.log.info('Creating a WooCommerce product from ebay id: %s' % (item_id))

        if self.does_product_exist(item_id):
            self.log.warning('Product with item id %d already exists, skipping' % (item_id))
            return self

        data = self.db_get_product_data(item_id)

        upload_data = {
            'name': data['title'],
            'type': 'simple',
            'short_description': data['condition_description'],
            'description': DEFAULT_DESCRIPTION,
            'sku': data['sku'],
        }

        # Add the category id
        category_id = self.get_mapped_category_id(data.get('category_id', 0))
        if category_id is not None:
            upload_data['categories'] = [{ 'id': category_id }]

        res = self.api.post('products', upload_data).json()

        if res.get('id', False):
            self.db_product_uploaded(res['id'], item_id)
        else:
            # Invalid or duplicate sku
            if res.get('code') == 'product_invalid_sku':
                if res.get('data') and res['data'].get('resource_id'):
                    new_post_id = res['data']['resource_id']
                    self.log.warning(
                        'The SKU for %s already exists for %s. Updating.' % (new_post_id, item_id))
                    self.db_product_uploaded(new_post_id, item_id)
            else:
                self.log.error('Unable to retrive product_id')
                self.log.debug(res)
                self.log.debug(upload_data)

        return self

    def delete_product_images(self, item_id):
        """
            With the provided `item_id`, an API request will
            be made to WooCommerce to identify all images
            associted with it. Then, it will delete each of
            those images.
        """

        pass

        # self.log.info('Deleting media %d from WordPress' % (image_id))
        # response = self.api.delete('media/%d' % (image_id), params={'force': True}).json()
        # self.log.debug(response)
        # return response

    def delete_product(self, item_id):
        """
            With the provided `item_id`, an API request will
            be made to WooCommerce to force delete the item

            The `item_id` is supplied by the queue, which gets
            them from `db.db_get_inactive_uploaded_item_ids()`

            When an item is force deleted, it will not appear
            in the "Trash"

            Returns the response as a dictionary or None if
            there is no post id
        """
        post_id = self.db_woo_get_post_id(item_id)
        if post_id is not None:
            self.log.info('Deleting %d from WooCommerce' % (item_id))
            response = self.api.delete('products/%d' % (post_id), params={'force': True}).json()

            self.delete_product_images(post_id)
            status_code = response.get('data', dict).get('staus', 500)

            if status_code == 404:
                self.log.warning("Product was already deleted")

            elif status_code < 300 and status_code > 199:
                self.log.info('Product deleted')

            else:
                self.log.debug(response)

            return response
        return None

    def delete_all_products_in_range(self, id_range, chunk_size=100):
        """
            With a provided `id_range`, which is expected to be
            a `range` or `list` type, multiple bulk requests
            will be made to the Woo Commerce API to delete
            those items.

            When `id_range` is of type(range), your ending ID needs
            to be the last ID to delete + 1

            Returns None
        """
        self.log.info('Deleting products from %d to %d' % (id_range[0], id_range[-1]))

        # The API says that it supports chunks up to 100 items, but in testing
        # it would always time out, even if it successfully deleted the items
        # with any chunk size greater than or equal to 50
        for chunk in self.__divide_into_chunks(id_range, chunk_size):
            post_ids = list(chunk)
            data = {
                'delete': post_ids
            }
            self.api.post('products/batch', data)
            self.log.info('Deleted ids %s' % (post_ids))

            for post_id in post_ids:
                self.delete_product_images(post_id)


    def update_product_metadata(self, item_id):
        post_id = self.db_woo_get_post_id(item_id)
        attributes = list()
        attributes_to_upload = list()

        if post_id is not None:
            attributes = self.db_get_all_product_metadata(item_id)

            # Strip out any pictures
            attributes = [
                attribute
                for attribute in attributes
                if attribute['key'] != 'picture_url'
            ]

            # Format the attributes in a way that WooCommerce is expecting
            for attribute in attributes:
                attributes_to_upload.append({
                    'name': attribute['key'],
                    'options': [
                        attribute['value']
                    ],
                    "visible": True,
                    "variation": False,
                })

            options = {
                'attributes': attributes_to_upload,
                'default_attributes': attributes_to_upload
            }
            self.api.put('products/%d' % (post_id), options).json()
            self.log.info("Attributes Added for item: %d" % (item_id))
        else:
            self.log.warning('The product %d has not yet been uploaded' % (item_id))

    def try_command(self, command, data):
        """
            Wrapper for running methods.

            Verifies that we support the method, raising a NameError if not
            and then runs the method specified in the `command` argument in
            a try, except statement

            `command` is a string that is inside `__available_commands`

            `data` is dependent on the type of command that is being ran.
            In most instances, it is an integer containing the ebay ItemID.

            With the `delete_all_products` command, it is either a range or
            a list containing the post ids for existing products
        """
        __available_commands = [
            'create_product',
            'delete_product',
            'upload_images',
            'delete_all_products',
            'upload_attributes',
        ]

        err_msg = "Command %s is unrecognized. Supported commands are: %s" % (
            command, ', '.join(__available_commands))

        if command not in __available_commands:
            self.log.exception(err_msg)
            raise NameError(err_msg)

        try:
            if command == 'create_product':
                return self.create_product(data)

            elif command == 'delete_product':
                return self.delete_product(data)

            elif command == 'upload_images':
                return self.upload_product_images(data)

            elif command == 'delete_all_products':
                return self.delete_all_products_in_range(data)
            elif command == 'upload_attributes':
                return self.update_product_metadata(data)

            else:
                self.log.exception(err_msg)
                raise NameError(err_msg)

        # The several kinds of timeout exceptions that are normally returned by the API
        except (timeout, ReadTimeoutError, requests.exceptions.ConnectTimeout, requests.exceptions.ReadTimeout):
            self.log.warning('The Previous request Timed Out. Waiting 5s before retrying')
            time.sleep(5)
            self.try_command(command, data)
