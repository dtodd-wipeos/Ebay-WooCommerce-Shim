#!/bin/bash
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

IMGNAME=alpine-ebay-woo-shim

# This step is to remove the stopped container from local docker inventory
# Required if we want to remove the image the container depends on
echo "Removing previous container - An error here is expected if never built"
docker ps -a | grep ${IMGNAME} | awk '{print $1}' | xargs docker rm

# This step is to remove the image the above container depends on
# We remove the image because every subsequent build will generate
# a new image. This can quickly reduce your available disk space
# if you are making a lot of builds (such as when testing)
echo "Removing previous build - An error here is expected if never built"
docker images | grep ${IMGNAME} | awk '{print $3}' | xargs docker rmi

echo "Building container with scripts from bin"
docker build --tag ${IMGNAME} .

echo "Running your application"
docker run --volume $(pwd):/opt ${IMGNAME}:latest
