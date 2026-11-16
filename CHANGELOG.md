# Changelog

## 0.1.0 (unreleased)

- Modules `openimages.cloud.index_info` (read and select the catalog index) and
  `openimages.cloud.glance_info` (find the openimages.cloud images of a project).
- Role `openimages.cloud.glance_image`: import images into Glance (sha256 checked, cosign
  signature verified when cosign is installed, Glance multihash compared with the index).
- Role `openimages.cloud.oic_sync`: install the oic-sync package and enable its timers
  (Proxmox VE, OpenStack).
