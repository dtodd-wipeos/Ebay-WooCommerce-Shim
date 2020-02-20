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

#### Wordpress

Unfortunately we can't use the WooCommerce API key and secret to authenticate with
the rest of the wordpress API, thus we can't upload images.

To get around this issue, we will communicate with the Wordpress API directly. We
will be using the wordpress plugins [JSON Basic Authentication](https://github.com/WP-API/Basic-Auth) and [Application Passwords](https://wordpress.org/plugins/application-passwords/).

1. Install and activate the above plugins. `JSON Basic Authentication` has to be downloaded in zip form from the linked github.
1. Create a user that (at the minimum) can create/edit posts.
1. Login as that user and use the sidebar to get to Users -> Your Profile
1. Scroll down to the section called "Application Passwords"
1. Give the password a good descriptive name (used so that you can easily identify the purpose, not authentication) and click "Add New"
1. Copy the password that you are given, including the spaces between the segments
1. Now you can use that password in combination with the username of the user for API requests
    * Note: This will **NOT** allow you to login to the UI with that password. It only authenticates API calls

The fields to set in the `creds.example` file are `wordpress_user` and `wordpress_app_password`. The wordpress blog is assumed to be at the same URL as the WooCommerce store.

### Development

1. Ensure that you have [Pipenv](https://github.com/pypa/pipenv) installed, in addition to Python 3.8
1. Install the necessary dependencies, this will also create a virtualenv to work from - `$ pipenv install`
1. Enter the virtualenv - `$ pipenv shell`
1. Copy the `credentials/creds.example` file to `credentials/creds.sandbox` and fill out the access keys
    * To use production credentials: Copy the `credentials/creds.example` file to `credentials/creds.production` and fill out the access keys
5. Start the server with `./run.sh sandbox`
    * To use production credentials instead: `./run.sh production`
    * If no arguments are supplied to `run.sh`, it will default to `production`

### Production

1. Ensure that you have [Docker](https://www.docker.com) installed, and that your user is in the `docker` group
1. Copy the `credentials/creds.example` file to `credentials/creds.production` and fill out the access keys
1. Build and start the docker container with `./build-container.sh`
    * Subsequent launches can be accomplished with `./run-container.sh`, which won't spend the time to build

The container is hardcoded to use the production credentials. Alter `CMD` line of the Dockerfile to change that to `sandbox` if you wish and rebuild.

## Configuration

There are a couple of files that are required to make this system work. These files are:
* `credentials/creds.production` - Production credentials. Also contains general variables such as locations of other needed files
* `database/ebay-to-woo-commerce-category-map.json` (or whatever is defined in `creds.production`) - This is a mapping of all categories from ebay listings to all that are configured in WooCommerce
* `database/ebay_items.db` (or whatever is defined in `creds.production`) - This is the local database that will contain all items, their metadata (picture URLs, and Item Specifics), and various internals for the application to recover if it crashes or hits rate limits

### Category Mapping

This is optional if you are fine with having all your products appear as "uncategorized". If you would prefer to have a mapping, get ready for some data entry.

First, get all categories from Woo-Commerce ([documented here](http://woocommerce.github.io/woocommerce-rest-api-docs/#list-all-product-categories)). You will need to request incrementing pages until you get nothing returned. The fields that are important are "id" and "name"; Name is only used so that you can identify the category in the future.

Once you have those fields, throw them into the mapping json file with `id` being changed to `wc-id`, and `name` being changed to `wc-name`.
Under every `wc-id` key, include a new key called `ebay_ids`, which contains a list (or array in JSON speak)

Now to fetch the categories that are in use. What I've done is fetch all products using `GetSellerList` and then issued a SQL query similar to the following:
`SELECT DISTINCT category_name, category_id from items where active = 'Active';` on the `ebay_items.db` database. 

Finally, populate the lists for the categories with ids that are close enough in terms of the category description
