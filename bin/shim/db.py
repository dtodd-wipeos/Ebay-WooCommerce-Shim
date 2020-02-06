#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import sys
import sqlite3
import logging

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
        log_handler = logging.StreamHandler(sys.stdout)
        log_format = logging.Formatter('%(asctime)s - %(name)s.%(funcName)s - %(levelname)s - %(message)s')
        log_handler.setFormatter(log_format)
        self.log.addHandler(log_handler)

        # Setup database
        # Used to convert datetime objects (and others in the future)
        detect_types = sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES
        # Store a local database of items as a cache. Autocommit is on
        self.database = sqlite3.connect(
            os.environ.get('database_file', 'database/ebay_items.db'),
            isolation_level=None,
            detect_types=detect_types)

        with self.database:
            self.cursor = self.database.cursor()
        self.__create_tables()

    def __create_tables(self):
        """
            Creates a table called `items` and another called `item_metadata`
            if they don't already exist in the selected database file

            `items` contains the primary information about items that we're
            interested in, while `item_metadata` contains a key-value store
            of ItemSpecifics, which is fluid and will generally contain specs
        """

        self.cursor.executescript("""
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

    def store_item_from_ebay(self, item):
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
                condition_description, description
            ) VALUES (
                :itemid, :active, :available_quantity,
                :title, :sku, :start_date, :end_date,
                :category_id, :category_name, :condition_name,
                :condition_description, :description)
        """

        values = {
            'itemid': int(item['ItemID']),
            'active': item['SellingStatus']['ListingStatus'],
            'available_quantity': int(item['Quantity']) - int(item['SellingStatus']['QuantitySold']),
            'title': item['Title'],
            'sku': item['SKU'],
            'start_date': isodate.parse_datetime(item['ListingDetails']['StartTime']),
            'end_date': isodate.parse_datetime(item['ListingDetails']['EndTime']),
            'category_id': int(item['PrimaryCategory']['CategoryID']),
            'category_name': item['PrimaryCategory']['CategoryName'],
            'condition_name': '',
            'condition_description': '',
            'description': '',
        }

        # These fields have a chance to not exist, so we set default empty values
        # and then try to add them after the dictionary is created
        if item.get('ConditionDisplayName', False):
            values['condition_name'] = item['ConditionDisplayName']
        if item.get('ConditionDescription', False):
            values['condition_description'] = item['ConditionDescription']
        if item.get('Description', False):
            values['description'] = item['Description']

        self.cursor.execute(query, values)

        return self

    def store_item_metadata_from_ebay(self, item):
        """
            Store the provided `item`, which is a dictionary,
            into the local database. We're specifically after
            metadata such as picture urls, and item specifics.

            When this is called from GetSellerList, the PictureDetails
            are what are normally provided. When this is called from
            GetItem, ItemSpecifics are what are normally provided
        """

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

        # PictureDetails exists on GetSellerList and GetItem, so this should always get hit
        if item.get('PictureDetails', False):
            self.log.debug('Found Picture Details for %d' % (int(item['ItemID'])))
            for picture in item['PictureDetails']['PictureURL']:
                values = {
                    'itemid': int(item['ItemID']),
                    'key': 'picture_url',
                    'value': picture,
                }

                metadata_count = len(
                    self.cursor.execute(query_for_existing, values).fetchall()
                )

                if metadata_count == 0:
                    self.cursor.execute(query_to_insert, values)
                else:
                    self.log.debug(has_metadata % (int(item['ItemID']), picture))

        # ItemSpecifics only exists on GetItem when `IncludeItemSpecifics` is True
        if item.get('ItemSpecifics', False):
            self.log.debug('Found Specific Details for %d' % (int(item['ItemID'])))
            for detail in item['ItemSpecifics']['NameValueList']:
                if type(detail['Value']) is list:
                    detail['Value'] = ', '.join(detail['Value'])

                values = {
                    'itemid': int(item['ItemID']),
                    'key': detail['Name'],
                    'value': detail['Value'],
                }

                metadata_count = len(
                    self.cursor.execute(query_for_existing, values).fetchall()
                )

                if metadata_count == 0:
                    self.cursor.execute(query_to_insert, values)
                else:
                    self.log.debug(has_metadata % (int(item['ItemID']), detail['Name']))

        return self
