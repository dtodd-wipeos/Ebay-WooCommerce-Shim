#!/bin/bash
# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

IMGNAME=alpine-ebay-woo-shim
BUILD_TARGET=run_app

function show_help() {
    echo "build-container.sh - Generates a local docker image called ${IMGNAME}"
    echo ""
    echo "Advanced Usage: $0 OPTIONS"
    echo ""
    echo "Available Options:"
    echo "  ?|-h|--help (optional), Shows this screen"
    echo "  -s|--stage (optional), Selects a particular stage to stop a build at"
    echo "      See the Dockerfile for all of the stages, default is run_app"
}

# Command line arguments
while [[ $# > 0 ]]; do
    key="$1"
    case $key in
        ?|-h|--help)
            show_help
            shift
            exit 0
        ;;
        # Give the ability to define which target to build (see the Dockerfile)
        -s|--stage)
            if [[ ! -z "$2" ]]; then
                BUILD_TARGET="$2"
            else
                echo "Invalid Argument: $1"
                show_help
                exit 1
            fi
            shift
        ;;
        *)
            echo "Invalid Argument: $1"
            show_help
            shift
            exit 1
        ;;
    esac
    shift
done

# This step is to remove the stopped container from local docker inventory
# Required if we want to remove the image the container depends on
docker ps -a | grep ${IMGNAME} > /dev/null
if [[ $? -eq 0 ]]; then
    echo "Removing previous container"
    docker ps -a | grep ${IMGNAME} | awk '{print $1}' | xargs docker rm
fi

# This step is to remove the image the above container depends on
# We remove the image because every subsequent build will generate
# a new image. This can quickly reduce your available disk space
# if you are making a lot of builds (such as when testing)
docker images | grep ${IMGNAME} > /dev/null
if [[ $? -eq 0 ]]; then
    echo "Removing previous build"
    docker images | grep ${IMGNAME} | awk '{print $3}' | xargs docker rmi
fi

echo "Building container with scripts from bin"
docker build --target ${BUILD_TARGET} --tag ${IMGNAME} .

echo "Running your application"
docker run \
      --volume $(pwd)/credentials:/opt/credentials \
      --volume $(pwd)/database:/opt/database \
      ${IMGNAME}:latest
