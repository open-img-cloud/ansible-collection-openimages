# openimages.cloud.oic_mirror

Run an internal mirror of the openimages.cloud catalog.

Runs `oic-sync mirror` under a system user with a hardened service and a daily timer, to a local directory (optionally served by an nginx server block) or an S3 bucket. Needs oic-sync 0.3.0 or newer.

Variables, with their types and defaults, are in
[`meta/argument_specs.yml`](meta/argument_specs.yml) (`ansible-doc -t role openimages.cloud.oic_mirror`).
Usage and examples: [collection README](https://github.com/open-img-cloud/ansible-collection-openimages#run-an-internal-mirror).
