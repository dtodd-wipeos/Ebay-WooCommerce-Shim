# Ebay -> WooCommerce Shim

This project's goal is to export active product listings from ebay into a local database, and import them into WooCommerce.

It will run as an isolated micro service, in a minimal, [Apline](https://alpinelinux.org/) based Docker container. At scheduled times,
it will update its database with ebay events (sold status, and new product listings), which will determine
what gets updated on the WooCommerce site.

## Getting Started

The workflow is mostly the same for development and production, except the goal for development is to not spend
a ton of time regenerating docker containers.

### Getting Access Keys

This project interfaces with both the Ebay API, and the WooCommerce API; both of which require the use of access keys.

The keys are stored in `credentials/creds.sandbox` and `credentials/creds.production`, which are bash files that are `source`d before running the server (or passed via environment variables to docker). There is a `credentials/creds.example` file that demonstrates the various environment variables that are used.

#### Ebay

If you do not already have an account with the ebay developers program, you can [sign up](https://developer.ebay.com/signin?tab=register) for free.

Once you are signed up, you will have to get a couple sets of [Access Keys](https://developer.ebay.com/my/keys). These are the sandbox and production keys.
The sandbox is used for development and testing, and has very liberal request limists compared to the production API.

Treat these keys with care, as they are what identifies your application. 

You will also need to request a [User Token](https://developer.ebay.com/my/auth/), which is how your ebay store talks with the application. Note that in the sandbox, your normal ebay login will not work.
A sandbox user has to be created, before you can request a token in the sandbox. This is where it is rather limited, as before you can get products or seller events, you must first list products with that sandbox user.

The user token should be just as restricted as the access keys, since the token can be used to do anything that user is normally capable of.

#### WooCommerce

WooCommerce uses several methods for authenticating API requests. In the scope of this project, we will only be using Wordpress' built in REST API.

1. Login to the wp-admin section of your web store as an administrative user
1. Use the sidebar to navigate to WooCommerce -> Settings -> Advanced -> REST API
1. Click on "Add key"
1. Select the user who will own the key (you should create one with limited scope, such as only being able to interact with WooCommerce)
1. Permissions should be set to Read/Write as we will be performing all of the CRUD actions
1. Description is a human readable identifier for the purpose of that API key
1. Click "Generate API key", and on the next screen copy the key and secret somewhere safe. They won't be shown again.

### Development

1. Ensure that you have [Pipenv](https://github.com/pypa/pipenv) installed, in addition to Python 3.8
1. Install the necessary dependencies, this will also create a virtualenv to work from - `$ pipenv install`
1. Enter the virtualenv - `$ pipenv shell`
1. Copy the `credentials/creds.example` file to `credentials/creds.sandbox` and fill out the access keys
    * To use production credentials: Copy the `credentials/creds.example` file to `credentials/creds.production` and fill out the access keys
5. Start the server with `./run.sh sandbox`
    * To use production credentials instead: `./run.sh production`

### Production

1. Ensure that you have [Docker](https://www.docker.com) installed, and that your user is in the `docker` group
1. Copy the `credentials/creds.example` file to `credentials/creds.production` and fill out the access keys
1. Build and start the docker container with `./build-container.sh`
    * Subsequent launches can be accomplished with `./run-container.sh`, which won't spend the time to build

The container is hardcoded to use the production credentials. Alter `CMD` line of the Dockerfile to change that to `sandbox` if you wish and rebuild.
