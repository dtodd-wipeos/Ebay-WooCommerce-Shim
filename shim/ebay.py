#!/usr/bin/env python3

import os
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError

class Ebay:
    def __init__(self):
        self.__available_commands = [
            'get_items'
        ]
        self.connection = self.__get_api_connection()
        self.seller_list = {}

    def __get_api_connection(self):
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
        return self.connection.execute(
            'GetSellerEvents',
            self.seller_list
        ).dict().get('ItemArray', None)

    def try_command(self, command):
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

