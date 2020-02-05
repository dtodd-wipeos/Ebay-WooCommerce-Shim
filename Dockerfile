# The very latest (possibly unstable) version of Alpine Linux
FROM alpine:edge

# Install python3 and pipenv
RUN apk add --no-cache python3 \
    && pip3 install pipenv

# Add the server, and shim library to a dir that is expected to be empty
ADD bin /opt

# All commands that follow this point will run as though we first did `cd /opt`
WORKDIR /opt

# Install dependencies, but only during `docker build`
COPY Pipfile Pipfile
RUN set -ex && pipenv install --deploy --system

# Start the server
ENTRYPOINT ["/opt/run-docker.sh"]
