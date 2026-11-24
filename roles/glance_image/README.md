# openimages.cloud.glance_image

Import openimages.cloud images into OpenStack Glance.

Checks the sha256 of the index, verifies the cosign signature when cosign is installed, sets the Glance properties and `min_ram` of the index, gives the images their stable names and compares the Glance multihash with the index. Needs the `openstack.cloud` collection and `openstacksdk`.

Variables, with their types and defaults, are in
[`meta/argument_specs.yml`](meta/argument_specs.yml) (`ansible-doc -t role openimages.cloud.glance_image`).
Usage and examples: [collection README](https://github.com/open-img-cloud/ansible-collection-openimages#import-images-into-glance).
