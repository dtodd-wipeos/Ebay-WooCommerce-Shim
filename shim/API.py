#!/usr/bin/env python3

import os
import datetime
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError

class APIShim:
    """
        Contains various methods for querying the ebay API
        that will get items that are currently active,
        categories, descriptions, etc
    """

    def __init__(self):
        """
            Contains the initial values that this object will
            have when it is created.
        """
        self.__available_commands = [
            'get_items'
        ]

        self.ebay = self.__get_api_connection()
        self.date_range = {}
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

    def __check_date_type(self, the_date=None):
        """
            Determines if the provided date is either a
            datetime object, a string, or NoneType.

            In the case that it's a datetime object, it
            gets returned. In the case it's a string,
            we attempt to convert it to a datetime object.

            In the case that either conversion fails, or
            `the_date` is None, today's datetime object
            is returned.
        """
        if the_date != None:
            if type(the_date) == type(datetime.datetime.today()):
                return the_date
            elif type(the_date) == type(''):
                try:
                    return datetime.datetime.strptime(the_date, '%Y-%m-%d')
                except ValueError:
                    return datetime.datetime.today()
        return datetime.datetime.today()

    def set_date_range(self, start_date=None, days=0, stop_date=None, range_type='Start'):
        """
            Creates a dictionary at `self.date_range` containing a from, to, and type

            `start_date` is optional, and when not defined defaults to today. Expected
            to be either a datetime object, or a date string.

            `days` is optional, and when not defined defaults to today. When it is
            defined, and `stop_date` is not defined, it will set the range from that.
            Negative numbers are supported, and when used, will reverse the start and
            stop dates

            `stop_date` is optional, and when not defined defaults to today + `days`.
            Expected to be either a datetime object, or a date string

            `range_type` is the key that will be searched for. Case Sensitive.
            Supported values are:

            `Start` (default) will search for listings that were started within the
            date range. `Mod` will search for listings that have been modified within the
            date range. `End` will search for listings that are ending within the date range.
        """

        start_date = self.__check_date_type(start_date)

        if stop_date != None:
            stop_date = self.__check_date_type(stop_date)
        else:
            # If the stop date was not defined, set the range
            # based on `days`, which defaults to the same day
            stop_date = start_date + datetime.timedelta(days)
        
        # Convert dates into ISO 8601 (required by the API)
        # Start date is at the absolute beginning of the day
        start_date = start_date.strftime('%Y-%m-%dT00:00:00.000Z')
        # Stop date is at the absolute end of the day
        stop_date = stop_date.strftime('%Y-%m-%dT23:59:59.999Z')

        # If the Stop date is in the past, reverse order
        if stop_date < start_date:
            stop_date, start_date = start_date, stop_date

        self.date_range = {
            'from': start_date,
            'to': stop_date,
            'type': range_type
        }

        return self

    def set_range_filter(self):
        """
            If `self.seller_list` already contains a date
            range filter, we need to remove those first,
            and then add the type to the front of the
            keywords (eg StartTimeFrom, StartTimeTo, etc)

            The filter will then be applied from `self.date_range`
        """

        filters = [
            'StartTimeFrom', 'StartTimeTo',
            'ModTimeFrom', 'ModTimeTo',
            'EndTimeFrom', 'EndTimeTo',
        ]

        # If there is already a date range filter on the seller list an
        # exception will be thrown. We can only search one type at a time
        for the_filter in filters:
            try:
                del self.seller_list[the_filter]
            except KeyError:
                continue

        self.seller_list[self.date_range['type'] + 'TimeFrom'] = self.date_range['from']
        self.seller_list[self.date_range['type'] + 'TimeTo'] = self.date_range['to']

        return self

    def __print_response(self, full=False):
        if self.ebay.warnings():
            print("Warnings" + self.ebay.warnings())

        if self.ebay.response.content:
            print("Call Success: %s in length" % (self.ebay.response.content))

        print("Response Code: %s" % (self.ebay.response_code()))
        print("Response XML: %s" % (self.ebay.response.dom()))

        if full:
            print(self.ebay.response.content)
            print(self.ebay.response.json())
            print("Response Reply: %s" % (self.ebay.response.reply))
        else:
            response = "%s" % (self.ebay.response.dict())
            reply = "%s" % (self.ebay.response.reply)
            print("Response Dictionary: %s..." % (response[:100]))
            print("Response Reply: %s..." % (reply[:100]))

        return self

    def __get_items(self):
        """
            Returns a dictionary containing all items that were found
            with the search filter, or None if no items were found
        """
        self.ebay.execute(
            'GetSellerEvents',
            self.seller_list
        ).dict().get('ItemArray', None)

        return self

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
                self.__get_items().__print_response()

        except ConnectionError as e:
            print(e)
            print(e.response.dict())

        return self
