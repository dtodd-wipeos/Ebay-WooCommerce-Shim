#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import json
import time
import sqlite3
import logging
import datetime

from .util import LOG_HANDLER

import isodate

class Database:
    """
        Provides common methods for interacting with the local
        database for both ebay (inserting) and WooCommerce (reading)
    """

    def __init__(self, *args, **kwargs):
        # Setup logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        self.log.addHandler(LOG_HANDLER)

        # Setup database
        # Used to convert datetime objects (and others in the future)
        detect_types = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        # Store a local database of items as a cache.
        self.__database = sqlite3.connect(
            os.environ.get('database_file', 'database/ebay_items.db'),
            isolation_level=None,
            detect_types=detect_types)

        with self.__database:
            # Get column names with select queries
            self.__database.row_factory = sqlite3.Row
            # Get a cursor to execute statements
            self.__cursor = self.__database.cursor()
        self.__create_tables()
        self.__migrate_tables()

    def __create_tables(self):
        """
            Creates a table called `items` and another called `item_metadata`
            if they don't already exist in the selected database file

            `items` contains the primary information about items that we're
            interested in, while `item_metadata` contains a key-value store
            of ItemSpecifics, which is fluid and will generally contain specs
        """

        self.__cursor.executescript("""
            CREATE TABLE IF NOT EXISTS items (
                itemid INTEGER PRIMARY KEY,
                active BOOLEAN,
                available_quantity INTEGER,
                title TEXT,
                sku TEXT,
                start_date TIMESTAMP,
                end_date TIMESTAMP,
                category_id INTEGER,
                category_name TEXT,
                condition_name TEXT,
                condition_description TEXT,
                description TEXT
            );

            CREATE TABLE IF NOT EXISTS item_metadata (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                itemid INTEGER,
                key TEXT,
                value TEXT
            );
        """)

    def __migrate_tables(self):
        """
            Automatically apply table migrations
            when the database is initalized
        """
        def get_version():
            """
                Returns the current Schema
            """
            self.__execute('PRAGMA user_version')
            return self.__cursor.fetchone()[0]

        def increment_version():
            """
                Increases the current Schema by 1
            """
            return "PRAGMA user_version = {v:d};".format(v=get_version() + 1)

        query = ""

        if get_version() < 1:
            """
                Track the post that is associated with the data;
                used to determine if we've uploaded the product
                (returns None if not)
            """
            query += """
                ALTER TABLE items ADD post_id INTEGER;
                ALTER TABLE item_metadata ADD post_id INTEGER;
            """
            query += increment_version()

        if get_version() < 2:
            """
                Track a couple internal state values to the ebay module

                `requests_today` is compared against when calling
                the ebay API and will stop the program if we reach
                `EbayShim().metadata_rate_limit`

                `got_item_ids` is a list of Item IDs that will be used
                to get ItemSpecific information for each item in the list.
                This is filled when the program reaches the rate limit so
                that it can continue where it left off the next day
            """
            query += """
                CREATE TABLE IF NOT EXISTS ebay_internals (
                    key CHAR PRIMARY KEY NOT NULL UNIQUE,
                    value TEXT NOT NULL
                );
                INSERT INTO ebay_internals
                    (key, value)
                VALUES ('requests_today', 0);
                INSERT INTO ebay_internals
                    (key, value)
                VALUES ('got_item_ids', '[]');
            """
            query += increment_version()

        if get_version() < 3:
            """
                Add more state internals, such as determining if we've
                already gotten the seller list today so that we can
                avoid un-necessary calls
            """
            query += """
                INSERT into ebay_internals
                    (key, value)
                VALUES ('got_seller_list_date', 'no');
            """
            query += increment_version()

        self.__cursor.executescript(query)

    def __execute(self, query, values={}):
        """
            Shortcut to execute an SQL `query`
            with `values` being an optional dictionary
            of named parameters (referenced in the
            query)

            Named parameters reduce the risk of SQL
            injection at the database level without
            having to steralize the content ourselves
        """
        return self.__cursor.execute(query, values)

    def __fetchall(self):
        """
            Shortcut to fetch all rows that were returned
            by a previous query

            Returns a list of dictionaries, where each
            dictionary contains the columns that were SELECTed
            if they were not None
        """
        return [ dict(row) for row in self.__cursor.fetchall() if row ]

    def __fetchone(self, key, default=None):
        """
            Shortcut to fetch one row that was returned
            by a previous query

            Returns the `key` from the dictionary if it
            exists, or `default` in the case it does not
        """
        return dict(self.__cursor.fetchone()).get(key, default)

    def __get_datetime_obj(self, time_string):
        """
            Parses an ISO 8601 date (such as provided by the ebay API)
            and returns a `datetime.datetime` object without the timezone

            We strip the timezone because sqlite's datetime parser doesn't
            know how to deal with them. Ebay's item times are always in UTC
        """
        return isodate.parse_datetime(time_string).replace(tzinfo=None)

    def db_store_item_from_ebay(self, item):
        """
            Store the provided `item`, which is a dictionary,
            into the local database. This gets all information
            that is normally returned from GetSellerList.

            For ItemSpecifics, we will have to make a seperate
            API call to GetItem with the DetailLevel set to
            ReturnAll (something that is not allowed on bulk
            queries such as GetSellerList and GetSellerEvents)
        """

        # INSERT OR REPLACE so that we can always ensure that the
        # saved information is up to date (or at least recent)
        query = """
            INSERT OR REPLACE INTO items (
                itemid, active, available_quantity,
                title, sku, start_date, end_date,
                category_id, category_name, condition_name,
                condition_description
            ) VALUES (
                :itemid, :active, :available_quantity,
                :title, :sku, :start_date, :end_date,
                :category_id, :category_name, :condition_name,
                :condition_description)
        """

        values = {
            'itemid': int(item['ItemID']),
            'active': item['SellingStatus']['ListingStatus'],
            'available_quantity': int(item['Quantity']) - int(item['SellingStatus']['QuantitySold']),
            'title': item['Title'],
            'sku': item['SKU'],
            'start_date': self.__get_datetime_obj(item['ListingDetails']['StartTime']),
            'end_date': self.__get_datetime_obj(item['ListingDetails']['EndTime']),
            'category_id': int(item['PrimaryCategory']['CategoryID']),
            'category_name': item['PrimaryCategory']['CategoryName'],
            'condition_name': '',
            'condition_description': '',
        }

        # These fields have a chance to not exist, so we set default empty values
        # and then try to add them after the dictionary is created
        if item.get('ConditionDisplayName', False):
            values['condition_name'] = item['ConditionDisplayName']
        if item.get('ConditionDescription', False):
            values['condition_description'] = item['ConditionDescription']

        self.__execute(query, values)

        return self

    def __store_key_value(self, item_id, key, value):
        has_metadata = "%d already has metadata for %s"

        # Determine if we already have a record that matches exactly
        query_for_existing = """
            SELECT * FROM item_metadata
            WHERE
                itemid = :itemid AND
                key = :key AND
                value = :value
        """

        query_to_insert = """
            INSERT INTO item_metadata (
                itemid, key, value
            ) values (:itemid, :key, :value)
        """

        values = {
            'itemid': int(item_id),
            'key': key,
            'value': value,
        }

        metadata_count = len(
            self.__execute(query_for_existing, values).fetchall()
        )

        if metadata_count == 0:
            self.__execute(query_to_insert, values)
        else:
            self.log.debug(has_metadata % (int(item_id), value))

    def db_store_item_metadata_from_ebay(self, item):
        """
            Store the provided `item`, which is a dictionary,
            into the local database. We're specifically after
            metadata such as picture urls, and item specifics.

            When this is called from GetSellerList, the PictureDetails
            are what are normally provided. When this is called from
            GetItem, ItemSpecifics are what are normally provided
        """

        # PictureDetails exists on GetSellerList and GetItem, so this should always get hit
        if item.get('PictureDetails', False):
            self.log.debug('Found Picture Details for %d' % (int(item['ItemID'])))
            if type(item['PictureDetails']['PictureURL']) is list:
                for picture in item['PictureDetails']['PictureURL']:
                    self.__store_key_value(item['ItemID'], 'picture_url', picture)

            # Case for only one picture being on a listing
            elif type(item['PictureDetails']['PictureURL']) is str:
                self.__store_key_value(
                    item['ItemID'], 'picture_url',
                    item['PictureDetails']['PictureURL'])

            else:
                err_msg = 'Unexpected type %s from PictureDetails. Expecting either list or str'
                self.log.error(err_msg % (type(item['PictureDetails']['PictureURL'])))


        # ItemSpecifics only exists on GetItem when `IncludeItemSpecifics` is True
        if item.get('ItemSpecifics', False):
            self.log.debug('Found Specific Details for %d' % (int(item['ItemID'])))
            if type(item['ItemSpecifics']['NameValueList']) is list:
                for detail in item['ItemSpecifics']['NameValueList']:
                    if type(detail['Value']) is list:
                        detail['Value'] = ', '.join(detail['Value'])

                    self.__store_key_value(item['ItemID'], detail['Name'], detail['Value'])

            # Case for only one ItemSpecifc field
            elif type(item['ItemSpecifics']['NameValueList']) is dict:
                values = item['ItemSpecifics']['NameValueList']

                if type(values['Value']) is list:
                    detail['Value'] = ', '.join(detail['Value'])
                
                self.__store_key_value(item['ItemID'], values['Name'], values['Value'])

            else:
                err_msg = 'Unexpected type %s from ItemSpecifics. Expecting either list or str'
                self.log.error(err_msg % (type(item['ItemSpecifics']['NameValueList'])))

        return self

    def db_get_product_data(self, item_id):
        """
            For the provided `item_id`, the local database
            is searched for the matching row and extracts it
            if one is found, and it has quantity and is marked
            as active

            Returns a dictionary containing the product data
            or an empty dictionary
        """
        query = """
            SELECT *
            FROM items
            WHERE
                available_quantity > 0 AND
                itemid = :item_id
            LIMIT 1
        """
        values = {
            'item_id': str(item_id),
        }

        self.__execute(query, values)
        return dict(self.__cursor.fetchone())

    def db_get_product_image_urls(self, item_id):
        """
            Gets all product image URLs that are
            associated with a particular `item_id`

            Returns a list containing one or more
            URLs to download images from, sorted
            alphabetically
        """

        query = """
            SELECT value, post_id FROM item_metadata
            WHERE
                itemid = :item_id AND
                key = 'picture_url'
            ORDER BY value;
        """

        values = {
            'item_id': str(item_id),
        }

        self.__execute(query, values)
        return self.__fetchall()

    def db_get_all_product_metadata(self, item_id):
        """
            For the provided `item_id`, the local database
            is searched for all occurrences of metadata that
            match, and extracts that if any are found

            Returns a list of dictionaries, where each dictionary
            is one key-value combination for the data stored
            or an empty list if nothing is found
        """
        query = "SELECT key, value FROM item_metadata WHERE itemid = :item_id;"
        values = {
            'item_id': str(item_id),
        }

        self.__execute(query, values)
        return self.__fetchall()

    def db_get_active_item_ids(self):
        """
            Searches the local database for all items that
            are marked as active

            Returns a list containing all the item ids
        """
        self.log.debug('Getting all active IDs')
        query = "SELECT itemid FROM items WHERE active = 'Active' AND post_id IS NULL;"

        self.__execute(query)
        item_ids = self.__cursor.fetchall()

        return [ i['itemid'] for i in item_ids if i['itemid'] ]

    def __mark_data_as_uploaded(self, data_type, post_id, item_id):
        """
            Meta method for `db_product_uploaded` and `db_metadata_uploaded`
            that sets the `post_id` field in the local database for the `item_id`

            This field is then checked before uploading the data, and
            skipped (by default) if the data has already been uploaded

            Returns `self`
        """
        if data_type == 'product':
            query = "UPDATE items SET post_id = :post_id WHERE itemid = :item_id;"
        elif data_type == 'metadata':
            query = "UPDATE item_metadata SET post_id = :post_id WHERE itemid = :item_id;"
        else:
            raise ValueError(
                'Incorrect data_type %s. Expected "product" or "metadata"' % (data_type)
            )

        values = {
            'post_id': post_id,
            'item_id': item_id,
        }

        self.__execute(query, values)

        return self

    def db_product_uploaded(self, post_id, item_id):
        """
            Shortcut to mark products as uploaded by storing the post it is a part of

            Returns `self`
        """
        return self.__mark_data_as_uploaded('product', post_id, item_id)

    def db_metadata_uploaded(self, post_id, item_id):
        """
            Shortcut to mark product metadata (such as images and attributes)
            as uploaded by storing the post it is a part of

            Returns `self`
        """
        return self.__mark_data_as_uploaded('metadata', post_id, item_id)

    def db_ebay_get_request_counter(self):
        """
            Returns an integer that is the total amount of requests today
        """
        query = "SELECT value FROM ebay_internals where key = 'requests_today'"
        self.__execute(query)
        return int(self.__fetchone('value', 0))

    def db_ebay_increment_request_counter(self):
        """
            For every request made to the ebay API
            (Currently only when getting metadata),
            we add one to the request counter

            Returns None
        """
        requests = self.db_ebay_get_request_counter()
        query = "UPDATE ebay_internals SET value = :requests WHERE key = 'requests_today'"
        self.__execute(query, {'requests': requests + 1,})
    
    def db_ebay_zero_request_counter(self):
        """
            Resets the request counter to 0

            The request counter is used to ensure that
            we don't make so many API requests to ebay
            that we hit the rate limit (5000 requests/day)

            Returns None
        """
        query = "UPDATE ebay_internals SET value = 0 WHERE key = 'requests_today'"
        self.__execute(query)

    def db_ebay_store_got_item_ids(self, item_ids):
        """
            Used to save the current state of the program
            whenever we hit a rate limit

            Returns None
        """
        query = "UPDATE ebay_internals SET value = :items WHERE key = 'got_item_ids'"
        self.__execute(query, {'items': json.dumps(item_ids),})

    def db_ebay_get_got_item_ids(self):
        """
            Provides a starting point for the program to
            continue from when it pulls the item metadata

            In the case that no ids were stored previously,
            this will default to all active items

            Returns a list of ebay item ids
        """
        query = "SELECT value FROM ebay_internals WHERE key = 'got_item_ids'"
        self.__execute(query)
        ids = json.loads(self.__fetchone('value', '[]'))

        if not ids:
            self.log.warning('No continue point, getting all active items')
            return self.db_get_active_item_ids()
        return ids

    def db_ebay_got_seller_list_date(self):
        """
            Provides a method for preventing the `get_seller_list` command
            from being ran multiple times a day

            Returns True when there is either no date, or the date was in
            the past. Returns False when there is a date that is today or
            in the future
        """
        query = "SELECT value FROM ebay_internals WHERE key = 'got_seller_list_date'"
        self.__execute(query)
        last_date = self.__fetchone('value', 'no')

        if last_date != 'no' and isodate.parse_date(last_date) >= datetime.date.today():
            msg = 'We already ran get_seller_list today (or in the future). Wait until tomorrow'
            self.log.warning(msg)
            return False

        if last_date == 'no' or isodate.parse_date(last_date) < datetime.date.today():
            query = "UPDATE ebay_internals SET value = :isodate WHERE key = 'got_seller_list_date'"
            today = isodate.date_isoformat(datetime.date.today())
            self.__execute(query, {'isodate': today})

            self.db_ebay_zero_request_counter()

        return True

    def db_woo_get_post_id(self, item_id):
        """
            Searches the database for `item_id`, and will
            return the value of the `post_id` column.

            If the product has not been uploaded to Woo Commerce,
            this will return None
        """
        query = "SELECT post_id FROM items WHERE itemid = :item_id"
        self.__execute(query, {'item_id': item_id})

        return self.__fetchone('post_id')

    def db_get_inactive_uploaded_item_ids(self):
        query = """
            SELECT itemid FROM items
            WHERE
                post_id is not NULL AND
                active != 'Active' OR
                end_date <= date('now')
        """
        self.__execute(query)
        item_ids = self.__fetchall()
        return [ i['itemid'] for i in item_ids if i['itemid'] ]
