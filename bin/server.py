#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import logging
import threading

from shim.ebay import EbayShim
from shim.queue import ProductUploadQueue

# Log to console
log_handler = logging.StreamHandler(sys.stdout)
log_format = logging.Formatter('%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s')
log_handler.setFormatter(log_format)

class Server:
    """
        Provides a framework for the threading of the server
    """

    def __init__(self):
        """
            Sets up internals, such as logging and a container
            for any threads that are running
        """
        # Set up logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        self.log.addHandler(log_handler)

        self.threads = []
        self.start()

    def __start_product_upload_queue(self):
        """
            Provides the bare minimum for `ProductUploadQueue`
            to function and start its own worker threads
            (default is 1)
        """
        # TODO: Populate this list directly from the database
        item_ids = [
            124070714664,
            124070794985,
            124070817266,
            124070858085,
            124070890853,
            124070906964,
            124071012427,
            124071844408,
            124071902830,
            124071918986,
            124071920856,
            124071965067,
            124071967215,
            124072021509,
            124072049703,
        ]

        ProductUploadQueue(item_ids).start()

    def __start_threads(self):
        """
            Starts a server thread for each "Queue" class
        """
        self.log.info('Starting background threads')

        # Start the ProductUploadQueue
        product_queue = threading.Thread(target=self.__start_product_upload_queue)
        product_queue.start()
        self.threads.append(product_queue)

        # TODO: Add the ebay download queue here

    def __finish_threads(self):
        """
            Blocks the parent thread until all children exit
        """
        self.log.info('Waiting for all threads to finish')
        for server_thread in self.threads:
            server_thread.join()

    def start(self):
        """
            Endpoint to kick off the server threads
            and block until they are complete

            Currently the only server thread is an
            instance of `ProductUploadQueue`, which
            itself will also spawn its own threads
            (default is 1).

            In the future, there will be another
            thread that will handle getting products
            from ebay and storing them in the database.

            There may also be another thread to provide
            a simple HTTP REST API
        """
        self.__start_threads()
        self.__finish_threads()

if __name__ == '__main__':
    Server()

    # Store all items that started within this date range
    # ebay_shim.set_date_range(start_date='2020-02-01', days=1).set_range_filter()
    # This will also store metadata for items that are still active
    # ebay_shim.try_command('get_seller_list')
