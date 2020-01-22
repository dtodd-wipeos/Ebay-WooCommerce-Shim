#!/usr/bin/env python3

import os
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError

class Ebay:
    """
        Contains methods for sending requests to the SDK

        Most will be private methods that use `try_command`
        as a wrapper. Currently we can get items for a specific
        date range (configured in shim.API.APIShim.set_range_filter)
    """
    def __init__(self):
        """
            Various constants and initial data that is used by the object
        """
        self.__available_commands = [
            'get_items'
        ]
        self.connection = self.__get_api_connection()
        self.seller_list = {}

    def __get_api_connection(self):
        """
            Creates a new connection to the ebay API (via the SDK)

            All parameters are set via environment variables (see creds.example)
        """
        return Trading(
            domain=os.environ.get('ebay_domain', False),
            # compatibility=int(os.environ.get('ebay_api_version', 648)),
            appid=os.environ.get('ebay_appid', False),
            certid=os.environ.get('ebay_certid', False),
            devid=os.environ.get('ebay_devid', False),
            token=os.environ.get('ebay_token', False),
            config_file=None,
            debug=False
        )

    def __get_items(self):
        """
            Returns a dictionary containing all items that were found
            with the search filter, or None if no items were found
        """
        return self.connection.execute(
            'GetSellerEvents',
            self.seller_list
        ).dict().get('ItemArray', None)

    def try_command(self, command):
        """
            Wrapper for running methods.

            Verifies that we support the method, raising a NameError if not
            and then runs the method specified in the `command` argument in
            a try, except statement

            `command` is a string that is inside `self.__available_commands`
        """
        err_msg = "Command %s is unrecognized. Supported queries are: %s" % (
            command, ', '.join(self.__available_commands))

        if command not in self.__available_commands:
            raise NameError(err_msg)

        try:
            if command == 'get_items':
                return self.__get_items()

        except ConnectionError as e:
            print(e)
            print(e.response.dict())

