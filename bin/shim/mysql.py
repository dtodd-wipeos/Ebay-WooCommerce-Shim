#!/usr/bin/env python3
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

import os
import logging

import mysql.connector

from .db import Database
from .util import LOG_HANDLER

class MySQLShim:

    def __init__(self, *args, **kwargs):
        # Setup logging
        self.log = logging.getLogger(__name__)
        self.log.setLevel(os.environ.get('log_level', 'INFO'))
        self.log.addHandler(LOG_HANDLER)

        self.sqlite = Database()

        self.mysql = mysql.connector.connect(
            host=kwargs.get('mysql_host', os.environ.get('mysql_host')),
            database=kwargs.get('mysql_db', os.environ.get('mysql_db')),
            user=kwargs.get('mysql_user', os.environ.get('mysql_user')),
            passwd=kwargs.get('mysql_pass', os.environ.get('mysql_pass')))
        self.cursor = self.mysql.cursor()

    def drop_tables(self):
        """
            If any of these tables exist on the destination
            mysql server, drop them.

            This should be considered a safe operation as
            the tables are recreated by this class
        """
        self.cursor.execute("DROP TABLE IF EXISTS ebay_internals")
        self.cursor.execute("DROP TABLE IF EXISTS items")
        self.cursor.execute("DROP TABLE IF EXISTS item_metadata")
        self.cursor.execute("DROP TABLE IF EXISTS sqlite_sequence")

    def create_tables(self):
        """
            Create the tables that we care about

            (this is basically just a conversion from sqlite to mysql)
        """
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS `items` (
                `item_id` bigint(20) DEFAULT NULL,
                `post_id` varchar(5) DEFAULT NULL,
                `active` varchar(9) DEFAULT NULL,
                `available_quantity` smallint(6) DEFAULT NULL,
                `title` varchar(80) DEFAULT NULL,
                `sku` varchar(46) DEFAULT NULL,
                `start_date` varchar(19) DEFAULT NULL,
                `end_date` varchar(19) DEFAULT NULL,
                `category_id` mediumint(9) DEFAULT NULL,
                `category_name` varchar(162) DEFAULT NULL,
                `condition_name` varchar(24) DEFAULT NULL,
                `condition_description` varchar(229) DEFAULT NULL,
                `description` varchar(0) DEFAULT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)
        self.cursor.execute("""
            CREATE TABLE IF NOT EXISTS `item_metadata` (
                `id` mediumint(9) DEFAULT NULL,
                `item_id` bigint(20) DEFAULT NULL,
                `post_id` varchar(0) DEFAULT NULL,
                `key` varchar(11) DEFAULT NULL,
                `value` varchar(102) DEFAULT NULL
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
        """)

    def insert_items(self):
        """
            Iterates over all products and metadata,
            packages it in a mysql query and inserts
            them as a bulk transaction
        """
        products_to_insert = list()
        metas_to_insert = list()

        for product in self.sqlite.db_get_all_items():
            products_to_insert.append((
                product.get('item_id'),
                product.get('post_id'),
                product.get('active'),
                product.get('available_quantity'),
                product.get('title'),
                product.get('sku'),
                product.get('start_date'),
                product.get('end_date'),
                product.get('category_id'),
                product.get('category_name'),
                product.get('condition_name'),
                product.get('condition_description'),
                product.get('description'),
            ))


        for product_meta in self.sqlite.db_get_all_item_metadata():
            metas_to_insert.append((
                product_meta.get('id'),
                product_meta.get('item_id'),
                product_meta.get('post_id'),
                product_meta.get('key'),
                product_meta.get('value'),
            ))

        product_query = """
            INSERT INTO `items`
            (
                item_id, post_id, active,
                available_quantity, title,
                sku, start_date, end_date,
                category_id, category_name,
                condition_name, condition_description,
                description
            ) VALUES (
                %s, %s, %s,
                %s, %s,
                %s, %s, %s,
                %s, %s,
                %s, %s, %s
            );
        """

        meta_query = """
            INSERT INTO `item_metadata`
            (id, item_id, post_id, key, value)
            VALUES (%s, %s, %s, %s, %s);
        """

        self.cursor.executemany(product_query, products_to_insert)
        self.mysql.commit()
        self.cursor.executemany(meta_query, metas_to_insert)
        self.mysql.commit()

    def sanity_check_products(self):
        query = "SELECT COUNT(id) FROM `items`;"
        self.cursor.execute(query)
        res = self.cursor.fetchall()

        if len(res) == len(self.sqlite.db_get_all_items()):
            return True
        return False

    def sanity_check_metas(self):
        query = "SELECT COUNT(id) FROM `item_metadata`;"
        self.cursor.execute(query)
        res = self.cursor.fetchall()

        if len(res) == len(self.sqlite.db_get_all_items()):
            return True
        return False