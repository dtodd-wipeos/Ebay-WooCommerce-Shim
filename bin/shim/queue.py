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
from .ebay import EbayShim
from .util import LOG_HANDLER

# I've had a hell of a time making the Queue
# work in the threadsafe way that it says it
# should in the documentation. So we're just
# doing a single thread that will handle the
# task of downloading images, creating
# products, and uploading images
MAX_WORKERS = 1

class BaseQueue:
    """
        Provides a base for common methods that are shared between the queues
    """

    def __init__(self, workers=MAX_WORKERS, *args, **kwargs):
        """
            Sets up internal information, such as the items
            to work on, and optionally how many worker threads
            to have (default of 1)
        """
        super(BaseQueue, self).__init__(*args, **kwargs)

        # Set up logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        self.log.addHandler(LOG_HANDLER)

        # Create a FIFO queue for what is being worked on
        self.queue = queue.Queue()
        # How many threads will we have? Defaults to `MAX_WORKERS`
        self.workers = workers
        # Might not be necessary, but allows us to perform
        # administrative stuff on a per-thread basis
        self.threads = []

    def __start_threads(self):
        """
            Start a worker thread until the maximum
            `self.workers` has been reached
        """
        self.log.info('Starting %d worker threads' % (self.workers))
        for _ in range(self.workers):
            worker_thread = threading.Thread(target=self.worker)
            worker_thread.start()
            self.threads.append(worker_thread)

    def __finish_queue(self):
        """
            Blocks the parent thread until the queue is empty
        """
        self.log.debug('Waiting for queue to empty')
        self.queue.join()
        for _ in range(self.workers):
            self.queue.put_nowait(None)

    def __finish_threads(self):
        """
            Blocks the parent thread until all children exit
        """
        self.log.info('Waiting for all threads to finish')
        for worker_thread in self.threads:
            worker_thread.join()

    def worker(self):
        """
            Provide a dummy worker, to be replaced by the inherting class
        """
        pass

    def start(self):
        """
            Endpoint to kick off the threads
            and block until they are complete

            HINT: You probably want to run this class
            in its own thread so as to not block the
            whole server
        """
        self.__start_threads()
        self.__finish_queue()
        self.__finish_threads()

class ProductUploadQueue(BaseQueue):
    """
        Provides a queue for adding products to WooCommerce
        and a method for processing the queue in parallel
    """

    def __init__(self, item_ids=None, workers=MAX_WORKERS, *args, **kwargs):
        """
            Sets up internal information, such as the items
            to work on, and optionally how many worker threads
            to have (default of 1)
        """
        super(ProductUploadQueue, self).__init__(workers=workers, *args, **kwargs)

        self.log.info('Populating queue with ebay item ids')

        if item_ids is None:
            item_ids = WooCommerceShim().db_get_active_item_ids()

        for item_id in item_ids:
            self.queue.put_nowait(item_id)

        self.start()

    def worker(self):
        """
            Creates an API connection to the database
            and runs the method to download images from
            ebay, upload the product data to woocommerce,
            and upload the images to wordpress

            This method will run in a seperate (non-blocking)
            thread until the queue gives a `None` object,
            signifying that it is empty
        """
        api = WooCommerceShim()

        while True:
            item_id = self.queue.get()
            if item_id is None:
                break

            api.create_product(item_id)

            self.queue.task_done()

class EbayDownloadQueue(BaseQueue):
    """
        Provides a queue for pulling products from ebay
        and a method for processing the queue in parallel
    """

    def __init__(self, workers=MAX_WORKERS, *args, **kwargs):
        """
            Sets up internal information, such as the items
            to work on, and optionally how many worker threads
            to have (default of 1)
        """
        super(EbayDownloadQueue, self).__init__(workers=workers, *args, **kwargs)

        self.queue.put('get_seller_list')
        self.queue.put('get_item_metadata')

        self.start()

    def worker(self):
        """
            Creates an API connection to the database
            and runs the method to download products from
            ebay, and download the product metadata from ebay

            This method will run in a seperate (non-blocking)
            thread until the queue gives a `None` object,
            signifying that it is empty

            Ultimately, this will just be a single thread that
            will first run `get_seller_list`, and then `get_item_metadata`
        """

        api = EbayShim()

        self.log.info('Setting date range filter to today and ending at 35 days in the future')
        api.set_date_range(start_date='', days=35, range_type='End').set_range_filter()

        while True:
            command = self.queue.get()
            if command is None:
                break

            api.try_command(command)

            self.queue.task_done()
