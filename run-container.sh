#!/bin/bash
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

echo "Running your application"
docker run \
       --volume $(pwd)/credentials:/opt/credentials \
       --volume $(pwd)/database:/opt/database \
       --network host \
       alpine-ebay-woo-shim:latest
