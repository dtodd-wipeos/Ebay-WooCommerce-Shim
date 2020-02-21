#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import logging
import threading

from shim.queue import (
    EbayDownloadQueue,
    ProductUploadQueue,
    ProductDeletionQueue,
    ProductImageQueue
)
from shim.util import LOG_HANDLER

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
        self.log.addHandler(LOG_HANDLER)

        self.threads = []
        self.start()

    def __start_threads(self):
        """
            Starts a server thread for each "Queue" class
        """
        self.log.info('Starting background threads')

        ebay_queue = threading.Thread(target=EbayDownloadQueue)
        self.threads.append(ebay_queue)

        product_upload_queue = threading.Thread(target=ProductUploadQueue)
        self.threads.append(product_upload_queue)

        product_delete_queue = threading.Thread(target=ProductDeletionQueue)
        self.threads.append(product_delete_queue)

        product_image_queue = threading.Thread(target=ProductImageQueue)
        self.threads.append(product_image_queue)

        # Actually start the threads
        ebay_queue.start()
        product_upload_queue.start()
        product_delete_queue.start()
        product_image_queue.start()

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
