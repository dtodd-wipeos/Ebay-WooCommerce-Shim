#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import sqlite3
import logging

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
            for detail in item['ItemSpecifics']['NameValueList']:
                if type(detail['Value']) is list:
                    detail['Value'] = ', '.join(detail['Value'])

                self.__store_key_value(item['ItemID'], detail['Name'], detail['Value'])

        return self

    def db_get_product_image_urls(self, item_id):
        """
            Gets all product image URLs that are
            associated with a particular `item_id`

            Returns a list containing one or more
            URLs to download images from, sorted
            alphabetically
        """

        query = """
            SELECT value FROM item_metadata
            WHERE
                itemid = :item_id AND
                key = 'picture_url'
            ORDER BY value;
        """

        values = {
            'item_id': str(item_id),
        }

        self.__execute(query, values)
        return self.__cursor.fetchall()

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

        query_for_metadata = """
            SELECT key, value FROM item_metadata
            WHERE itemid = :item_id;
        """

        self.__cursor.execute(query, {'item_id': str(item_id),})
        the_product = self.__cursor.fetchone()

        product = {
            'name': the_product[2],
            'type': 'simple',
            'description': the_product[8],
            'short_description': the_product[7],
        }

        return product
