# openimages.cloud.oic_sync

Install oic-sync and its systemd timer.

Installs [oic-sync](https://github.com/open-img-cloud/oic-sync) from its signed packages on a Proxmox VE node or a Debian or EL host, writes its configuration and enables its daily timer. `oic_sync_configure: false` installs the package only.

Variables, with their types and defaults, are in
[`meta/argument_specs.yml`](meta/argument_specs.yml) (`ansible-doc -t role openimages.cloud.oic_sync`).
Usage and examples: [collection README](https://github.com/open-img-cloud/ansible-collection-openimages#install-oic-sync-proxmox-ve-openstack).
