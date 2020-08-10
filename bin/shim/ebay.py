#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

# Standard Library modules
import os
import sys
import time
import logging
import datetime

from requests import exceptions

# Local modules
from .db import Database
from .util import LOG_HANDLER

# External modules
from ebaysdk.trading import Connection as Trading
from ebaysdk.exception import ConnectionError

class EbayShim(Database):
    """
        Contains various methods for querying the ebay API
        that will get items that are currently active,
        categories, descriptions, etc
    """

    def __init__(self, *args, **kwargs):
        """
            Contains the initial values that this object will
            have when it is created.
        """

        # Initalize the database and logging
        super(EbayShim, self).__init__(*args, **kwargs)

        # Setup logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        self.log.addHandler(LOG_HANDLER)

        # Setup Internals
        # Contains the range of listings to search (defined at `set_date_range`)
        self.date_range = {}
        # Contains the filters that are applied to
        # seller events searching (defined at `set_range_filter`)
        self.seller_filter_dict = {}
        # Contains all item ids that are currently active (defined at `get_item_ids`)
        self.got_item_ids = self.db_ebay_get_got_item_ids()

        # Used to determine how many times a paginated request
        # needs to be repeated to get the full data set
        self.pagination_total_items = 0
        self.pagination_total_pages = 0
        self.pagination_received_items = 0

        self.rate_limit = 1000

        # Setup connection to SDK
        self.ebay = self.__get_api_connection()

    def __get_api_connection(self):
        """
            Creates a new connection to the ebay API (via the SDK)

            All parameters are set via environment variables (see creds.example)
        """
        self.log.info('Opening new API connection to %s' % (os.environ.get('ebay_domain', False)))
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
                self.log.debug('Provided date is a datetime object, passing it through')
                return the_date
            elif type(the_date) == type(''):
                warning = 'Provided date %s is a string, attempting conversion' % (the_date)
                self.log.warning(warning)
                try:
                    return datetime.datetime.strptime(the_date, '%Y-%m-%d')
                except ValueError:
                    self.log.warning('Unable to convert, defaulting to today')
                    return datetime.datetime.today()
        self.log.warning('No Date provided, defaulting to today')
        return datetime.datetime.today()

    def set_date_range(self, start_date=None, days=0, stop_date=None, range_type='Start'):
        """
            Creates a dictionary at `self.date_range` containing a from, to, and type

            `start_date` is optional, and when not defined defaults to today. Expected
            to be either a datetime object, or a date string.

            `days` is optional, and when not defined defaults to the same date as the
            `start_date`. When it is defined, and `stop_date` is not defined, it will
            set the range from that. Negative numbers are supported, and when used,
            will reverse the start and stop dates

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
            self.log.warning('No Stop Date provided, defaulting to Start Date + %d' % (days))
            stop_date = start_date + datetime.timedelta(days)
        
        # Convert dates into ISO 8601 (required by the API)
        # Start date is at the absolute beginning of the day
        start_date = start_date.strftime('%Y-%m-%dT00:00:00.000Z')
        # Stop date is at the absolute end of the day
        stop_date = stop_date.strftime('%Y-%m-%dT23:59:59.999Z')

        # If the Stop date is in the past, reverse order
        if stop_date < start_date:
            self.log.info('Stop Date is before Start Date, swapping places')
            stop_date, start_date = start_date, stop_date

        self.date_range = {
            'from': start_date,
            'to': stop_date,
            'type': range_type
        }

        return self

    def set_range_filter(self):
        """
            If `self.seller_filter_dict` already contains a date
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
                del self.seller_filter_dict[the_filter]
                self.log.debug('Filter: %s was already in the seller list, deleted' % (the_filter))
            except KeyError:
                continue

        self.seller_filter_dict[self.date_range['type'] + 'TimeFrom'] = self.date_range['from']
        self.seller_filter_dict[self.date_range['type'] + 'TimeTo'] = self.date_range['to']

        return self

    def __update_pagination(self, entries=100):
        """
            Adds the pagination requirements to the seller_list dictionary
            (used in requests such as `GetSellerEvents` and `GetSellerList`)

            `entries` is the maximum number of items to return per page.
            The maximum value allowed by the API is 200, default is 25

            https://developer.ebay.com/Devzone/XML/docs/Reference/eBay/GetSellerList.html#Request.Pagination.EntriesPerPage
        """
        if entries > 200:
            self.log.warning('Too many entries requested per page. Maximum is 200 items. Defaulting to 100')
            entries = 100

        if not self.seller_filter_dict.get('Pagination', False):
            self.log.info('Pagination value not set in seller_filter, setting defaults')
            self.seller_filter_dict['Pagination'] = {
                'EntriesPerPage': entries,
                'PageNumber': 1,
            }
        else:
            if self.pagination_total_pages > self.seller_filter_dict['Pagination']['PageNumber']:

                pages_left = (self.pagination_total_pages -
                              self.seller_filter_dict['Pagination']['PageNumber'])
                self.log.info('%d Pages left' % (pages_left))

                if self.pagination_total_items > self.pagination_received_items:

                    items_left = self.pagination_total_items - self.pagination_received_items
                    self.log.info('%d Items left to get' % (items_left))

                    self.seller_filter_dict['Pagination']['PageNumber'] += 1
                else:
                    self.pagination_received_items = 0
                    self.pagination_total_items = 0
            else:
                self.pagination_total_pages = 0
        
        return self

    def get_item_metadata(self):
        """
            Iterates over all of the active items (`self.got_item_ids`)
            and makes an API request to get the ItemSpecifics (details
            such as the specs of the device, etc). These requests are
            then stored in the item_metadata table.

            If `self.got_item_ids` does not contain at least one item,
            it will be populated with all items that are marked as active
        """

        if not self.got_item_ids:
            self.got_item_ids = self.db_get_active_item_ids()

        if self.got_item_ids:
            for item_id in self.got_item_ids:
                # Remove the current item so that we can store the state
                self.got_item_ids.remove(item_id)

                if self.db_ebay_get_request_counter() >= self.rate_limit:
                    self.log.error('Rate limit reached! Storing the remaining ids for next run')
                    self.db_ebay_store_got_item_ids(self.got_item_ids)
                    break

                # Get the item, with specifc details (specs)
                # Arguments are defined here:
                # https://developer.ebay.com/Devzone/XML/docs/Reference/eBay/GetItem.html#Request.IncludeItemSpecifics
                result = self.ebay.execute(
                    'GetItem',
                    {
                        'IncludeItemSpecifics': True,
                        'ItemID': item_id,
                    }
                ).dict()['Item']

                self.db_ebay_increment_request_counter()
                self.db_store_item_metadata_from_ebay(result)

        if self.got_item_ids:
            self.db_ebay_store_got_item_ids([])

        return self

    def get_seller_list(self):
        """
            Gets multiple items from the same seller based on the date range
        """
        # Default the DetailLevel if it isn't already set
        # 'ItemReturnDescription' gives us the HTML of the
        # description, among other useful information
        if not self.seller_filter_dict.get('DetailLevel', False):
            self.seller_filter_dict['DetailLevel'] = 'ItemReturnDescription'

        # Call `__get_seller_list` sequentially to move to the next page
        self.__update_pagination()

        if self.db_ebay_get_request_counter() >= self.rate_limit:
            self.log.error('Rate limit reached! Not getting more items!')
            # Introduce a fake value to the pagination to
            # trick `try_command` to break out of the loop
            self.pagination_received_items = self.pagination_total_items + 1
            return None

        # Run the API request
        result = self.ebay.execute('GetSellerList', self.seller_filter_dict).dict()

        # Record that we sent a request to the ebay API
        self.db_ebay_increment_request_counter()

        # Determine where we are for pagination
        self.pagination_total_items = int(result['PaginationResult']['TotalNumberOfEntries'])
        self.pagination_total_pages = int(result['PaginationResult']['TotalNumberOfPages'])
        self.pagination_received_items += int(result['ReturnedItemCountActual'])

        msg = 'Got %d items out of %d total from the provided date range filter'
        self.log.info(msg % (self.pagination_received_items, self.pagination_total_items))

        item_list = result.get('ItemArray', None)
        if item_list is not None:
            items_active, items_inactive = 0, 0

            # Ensure that the response is a list containing one or more dictionaries
            try:
                for key in item_list['Item']:
                    _ = key['ItemID']
            except TypeError:
                # Only one item was returned
                item_list = [ item_list['Item'] ]
            else:
                item_list = item_list['Item']

            for item in item_list:
                # Store the items in the database for use in syncing to wordpress
                self.db_store_item_from_ebay(item)

                if item['SellingStatus']['ListingStatus'] == 'Active':
                    items_active += 1
                    # Store the metadata for active items only
                    self.db_store_item_metadata_from_ebay(item)
                    # Store active item ids so that we can fetch ItemSpecifics
                    self.got_item_ids.append(item['ItemID'])
                else:
                    items_inactive += 1
                    self.log.debug(
                        'Item %s is not active, not getting its metadata' % (item.get('ItemID'))
                    )

            msg = '%d Items Active and %d Items inactive'
            self.log.info(msg % (items_active, items_inactive))
        else:
            self.log.error('Got no items from the search. Try adjusting the date range')

        # if len(self.got_item_ids) > 0:
        #     self.get_item_metadata()

        return self

    def __print_response(self, full=False):
        if self.ebay.warnings():
            for warning in self.ebay.warnings().split(','):
                self.log.warning(warning)

            print("Warnings" + self.ebay.warnings())

        if self.ebay.response.content and full:
            print("Call Success: %s in length" % (self.ebay.response.content))

        self.log.info("Response Code: %s" % (self.ebay.response_code()))

        if full:
            self.log.debug(self.ebay.response.content)
            self.log.debug(self.ebay.response.json())
            self.log.debug("Response Reply: %s" % (self.ebay.response.reply))
        else:
            response = "%s" % (self.ebay.response.dict())
            reply = "%s" % (self.ebay.response.reply)
            self.log.debug("Response Dictionary: %s..." % (response[:100]))
            self.log.debug("Response Reply: %s..." % (reply[:100]))

        return self

    def try_command(self, command):
        """
            Wrapper for running methods.

            Verifies that we support the method, raising a NameError if not
            and then runs the method specified in the `command` argument in
            a try, except statement

            `command` is a string that is inside `__available_commands`
        """
        __available_commands = [
            'get_seller_list',
            'get_item_metadata',
        ]

        err_msg = "Command %s is unrecognized. Supported commands are: %s" % (
            command, ', '.join(__available_commands))

        if command not in __available_commands:
            self.log.debug(err_msg)
            raise NameError(err_msg)

        try:
            if command == 'get_seller_list':
                if self.db_ebay_got_seller_list_date():
                    # We need to run this at least once to populate
                    # `self.pagination_total_items` and `self.pagination_received_items`
                    self.get_seller_list().__print_response()

                    # If there are still items to get, get them
                    while self.pagination_received_items < self.pagination_total_items:
                        self.get_seller_list().__print_response()
                else:
                    self.log.warning("Get Seller List already ran today. Skipping")

            elif command == 'get_item_metadata':
                self.get_item_metadata()

            else:
                self.log.debug(err_msg)
                raise NameError(err_msg)

        except ConnectionError as e:
            self.log.exception(e)
            self.log.exception(e.response.dict())

        except exceptions.ReadTimeout:
            self.log.exception('The Previous request Timed Out. Waiting 5s before retrying')
            time.sleep(5)
            self.try_command(command)

        except NameError:
            pass

        return self
