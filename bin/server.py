#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import queue
import logging
import threading

from shim.ebay import EbayShim
from shim.woo import WooCommerceShim

MAX_WORKERS = 4

class ProductQueue:
    def __init__(self):
        # Create a queue for products
        self.product_queue = queue.Queue()
        self.threads = []

    def product_creation_worker(self):
        woo_shim = WooCommerceShim()

        while True:
            # Pop an item off of the queue
            item_id = self.product_queue.get()
            if item_id is None:
                break

            log.debug('Creating item_id from item id: %d' % (item_id))

            # Create the product and upload the image(s)
            woo_shim.create_product(item_id)

            # This item is done, move to the next one
            self.product_queue.task_done()

    def product_queue_handler(self, item_ids):
        # Put the products into the Queue
        log.info('Populating queue with ebay item ids')
        for item_id in item_ids:
            self.product_queue.put_nowait(item_id)

        # Start the worker threads
        log.info('Starting %d worker threads' % (MAX_WORKERS))
        for _ in range(MAX_WORKERS):
            t = threading.Thread(target=ProductQueue.product_creation_worker, args=(self,))
            t.start()
            self.threads.append(t)

        # Wait for the queue to be exhausted
        log.debug('Waiting for queue to empty')
        self.product_queue.join()
        for _ in range(MAX_WORKERS):
            self.product_queue.put_nowait(None)

        log.info('Waiting for all threads to finish')
        for t in self.threads:
            t.join()

if __name__ == '__main__':

    # Log to console
    log_handler = logging.StreamHandler(sys.stdout)
    log_format = logging.Formatter('%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s')
    log_handler.setFormatter(log_format)

    # Set up logging
    log = logging.getLogger(__name__)
    log.setLevel(os.environ.get('log_level', 'INFO'))
    log.addHandler(log_handler)

    # Ebay item ids to upload
    item_ids = [
        124070714664,
        124070794985,
        124070817266,
        124070858085,
        124070890853,
        # 124070906964,
        # 124071012427,
        # 124071844408,
        # 124071902830,
        # 124071918986,
        # 124071920856,
        # 124071965067,
        # 124071967215,
        # 124072021509,
        # 124072049703,
    ]

    ProductQueue().product_queue_handler(item_ids)

    # Store all items that started within this date range
    # ebay_shim.set_date_range(start_date='2020-02-01', days=1).set_range_filter()
    # This will also store metadata for items that are still active
    # ebay_shim.try_command('get_seller_list')
