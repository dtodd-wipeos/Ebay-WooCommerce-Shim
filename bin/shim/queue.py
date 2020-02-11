#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import queue
import logging
import threading

from .woo import WooCommerceShim

MAX_WORKERS = 4

class ProductQueue:
    def __init__(self):
        # Log to console
        log_handler = logging.StreamHandler(sys.stdout)
        log_format = logging.Formatter('%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(log_format)

        # Set up logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        self.log.addHandler(log_handler)

        # Create a queue for products
        self.queue = queue.Queue()
        self.threads = []

    def worker(self):
        woo_shim = WooCommerceShim()

        while True:
            # Pop an item off of the queue
            item_id = self.queue.get()
            if item_id is None:
                break

            self.log.debug('Creating item_id from item id: %d' % (item_id))

            # Create the product and upload the image(s)
            woo_shim.create_product(item_id)

            # This item is done, move to the next one
            self.queue.task_done()

    def handler(self, item_ids):
        # Put the products into the Queue
        self.log.info('Populating queue with ebay item ids')
        for item_id in item_ids:
            self.queue.put_nowait(item_id)

        # Start the worker threads
        self.log.info('Starting %d worker threads' % (MAX_WORKERS))
        for _ in range(MAX_WORKERS):
            t = threading.Thread(target=self.worker)
            t.start()
            self.threads.append(t)

        # Wait for the queue to be exhausted
        self.log.debug('Waiting for queue to empty')
        self.queue.join()
        for _ in range(MAX_WORKERS):
            self.queue.put_nowait(None)

        self.log.info('Waiting for all threads to finish')
        for t in self.threads:
            t.join()
