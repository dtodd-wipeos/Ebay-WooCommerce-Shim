#!/bin/bash
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

CREDTYPE=production
CONTAINER='yes'

if [[ $# -eq 1 ]]; then
    CREDTYPE=$1
elif [[ $# -eq 2 ]]; then
    CREDTYPE=$1
    CONTAINER='no'
else
    echo "Too many arguments!"
    exit 1
fi

source ./credentials/creds.${CREDTYPE}

if [[ ${CONTAINER} == 'yes' ]]; then
    python3 server.py
else
    python3 bin/server.py
fi
