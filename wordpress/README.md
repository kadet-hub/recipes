# wordpress

WordPress 7.1.4 on PHP 8.5 and Apache with its `wp-content` on a claim,
designed in kadet-hub on the Docker Official Image and rendered by the
kadet-hub `kubernetes` generator 1.14.0. The database is the included
recipe `mariadb`.

Source: `docker.io/library/wordpress:7.1.4-php8.5-apache@sha256:41666f6d61dd038f87ceacd6323685bd9818a3a9b3d80d98af3ce9797c403dce`

Level: `deploys`

The WordPress project publishes no chart, Kustomize base, compose file or
image for a site. The compose file of
[WordPress/wordpress-develop](https://github.com/WordPress/wordpress-develop)
runs the development environment of WordPress core from the repository's
checkout. The Docker Official Image `wordpress` packages every release.
docker-library maintains it in
[docker-library/wordpress](https://github.com/docker-library/wordpress), as
it does `rabbitmq`'s, so the recipe is designed on that image (DEC-110 in
[docs/specs/recipes.md](../docs/specs/recipes.md)). The image's
documentation is its [Docker Hub page](https://hub.docker.com/_/wordpress).
WordPress is GPL-2.0-or-later. The recipe follows the newest WordPress
release on PHP 8.5, the PHP release with active support until 2027-12-31.
The digest is that of the index for linux/amd64, linux/arm/v5,
linux/arm/v7, linux/arm64/v8, linux/386, linux/ppc64le, linux/riscv64 and
linux/s390x.

The recipe can stand in for Bitnami's `wordpress` chart with its MariaDB.
Moving a release of that chart to the recipe is not tested.

## Include

```yaml
classes:
  - recipes.wordpress
parameters:
  namespace: wordpress
  kapitan:
    vars:
      target: wordpress
  applications:
    mariadb:
      password: <ref>
      root_password: <ref>
    wordpress:
      auth_key: <ref>
      secure_auth_key: <ref>
      logged_in_key: <ref>
      nonce_key: <ref>
      auth_salt: <ref>
      secure_auth_salt: <ref>
      logged_in_salt: <ref>
      nonce_salt: <ref>
```

The recipe includes `recipes.mariadb`. Pin `mariadb` in the fetch inventory next to this recipe, as an `oci` dependency at the
digest this version's index record lists under `includes`, with
`output_path: inventory/classes/recipes/<recipe>`. The recipe's page on
kadet-hub.org shows the whole fetch inventory.

## Required parameters

The eight keys and salts of `wp-config.php` must be set:
`applications.wordpress.auth_key`, `applications.wordpress.secure_auth_key`,
`applications.wordpress.logged_in_key`, `applications.wordpress.nonce_key`,
`applications.wordpress.auth_salt`, `applications.wordpress.secure_auth_salt`,
`applications.wordpress.logged_in_salt` and
`applications.wordpress.nonce_salt`. Each is a long random string, such as the values that
`https://api.wordpress.org/secret-key/1.1/salt/` generates. WordPress
signs its login cookies with them, so a change logs every user out. The
included recipe `mariadb` requires `applications.mariadb.password`, the
password with which WordPress connects as the user `app`, and
`applications.mariadb.root_password`. Set all of them as refs with the
backend of your choice. Without them the compile stops with
`Interpolation key 'applications.wordpress.auth_key' not found`.

The recipe does not install WordPress. The first visitor of
`/wp-admin/install.php` names the site and creates the admin account, so
install it before the Service is reachable by others.

## Settings

| Setting | Inventory |
|---|---|
| WordPress and PHP version | `components.wordpress.image`, tag and digest |
| `wp-content` volume size, 8Gi | `components.wordpress.volume_claims.data.spec.resources.requests.storage` |
| resources | `components.wordpress.resources` |
| further `wp-config.php` settings, such as `WP_HOME` | `components.wordpress.env.WORDPRESS_CONFIG_EXTRA`, PHP that `wp-config.php` runs |
| table prefix, `wp_` | `components.wordpress.env.WORDPRESS_TABLE_PREFIX` |
| database, its user and both passwords | the settings of `mariadb` |

The tag names the PHP version, and Renovate keeps it. Pick another PHP
version with a tag such as `7.1.4-php8.4-apache` when a plugin needs it.

The core files come from the image at every start of the pod, and
`wp-config.php` from the environment. Only `wp-content`, with uploads,
plugins and themes, lives on the claim. WordPress's automatic core updates
are on, as in the image, but they write into the container and are lost
with the pod. A new WordPress version comes with the image tag. After it,
open `/wp-admin/` once if WordPress asks to update its database.

The site URL is the URL the installation was opened at. Exposing the
Service, such as with an Ingress or a route, is left to the target.
`wp-config.php` turns on HTTPS when a proxy sends
`X-Forwarded-Proto: https`.

The pod runs as the image's user `www-data`, UID 33, and passes Pod
Security `restricted`. Apache binds port 80 as that user because the pod
sets the sysctl `net.ipv4.ip_unprivileged_port_start` to 0, which
`restricted` allows. As that user the image's entrypoint stops on a
`wp-content` that another user owns, such as the root of a new volume. The
init container `wp-content` therefore creates the directory `wp-content`
on the claim as `www-data`, and the pod mounts it from there. WordPress
connects to MariaDB without TLS.

The readiness probe gets `/wp-login.php` every 10 seconds. It fails while
WordPress cannot reach its database. There is no liveness probe, which
would restart WordPress during a database outage.

## Proof

`check wordpress --level deploys` with `tests/target.yml` on kind for each
Kubernetes minor CI tests. The image has no Kubernetes objects to compare
with, so the recipe is proven by deploying it (RCP-44). `tests/smoke`
checks that the pods of WordPress and MariaDB pass Pod Security
`restricted`. From a pod of the WordPress image, through the Service
`wordpress` on port 80, it installs WordPress through
`/wp-admin/install.php`, requires the image tag's version on the front
page, gets no session for a wrong password and logs in. Through the REST
API with the login's cookie it publishes a post, which it reads without
the session on its permalink, and uploads a PNG, which it fetches byte for
byte. It deletes the pod `wordpress-0` and reads the post and the PNG again
once the new pod is ready, and reaches `/wp/v2/users/me` with the same
session.
