# Part of Ebay-WooCommerce-Shim
# Copyright 2020 David Todd <dtodd@oceantech.com>
# License: Properitary

# This is a multi-stage docker file, each stage is a different section wrapped in comments
# https://docs.docker.com/develop/develop-images/multistage-build/

# Install the minimum required dependencies
FROM alpine:edge AS install_base_depends
RUN apk add --no-cache bash python3 libxslt
# End install minimum dependencies

# Create build dependencies stage
FROM install_base_depends AS install_build_depends
# These dependencies are used to compile pylibxml and multidict (there are no binaries available apparently)
RUN apk add --no-cache python3-dev build-base musl-dev libffi-dev libxml2-dev libxslt-dev
# End build dependencies

# Install upgrade pip to latest version
FROM install_build_depends AS upgrade_pip
# Pip keeps complaining about the version that ships with python3, so update it
RUN pip3 install --no-cache-dir --upgrade pip
# End upgrade pip

# Install pipenv
FROM upgrade_pip AS install_pipenv
RUN pip3 install --no-cache-dir pipenv
# End install pipenv

# Install and build any python wheels (binaries)
FROM install_pipenv AS install_depends
COPY Pipfile* /opt/
# From this point on, all future commands are ran from /opt
WORKDIR /opt
RUN set -ex && pipenv install --deploy --system --clear
# End install and build python wheels

# Remove build artifacts (source, toolchains, etc)
FROM install_depends AS remove_build_depends
RUN apk del python3-dev build-base musl-dev libffi-dev libxml2-dev libxslt-dev
# End remove build artifacts

# Build the application
FROM remove_build_depends AS build_app
ADD ./bin /opt
# End build application

# Run the app
FROM build_app AS run_app
ENTRYPOINT ["bash"]
CMD ["./run.sh production"]
# End run the app
