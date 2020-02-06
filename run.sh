#!/bin/bash
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

if [[ $# -eq 0 ]]; then
    source bin/run.sh $1 1
else
    source bin/run.sh production 1
fi
