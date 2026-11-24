# Changelog

## 0.1.0 (2026-11-24)

- Modules `openimages.cloud.index_info` (read and select the catalog index) and
  `openimages.cloud.glance_info` (find the openimages.cloud images of a project).
- Role `openimages.cloud.glance_image`: import images into Glance (sha256 checked, cosign
  signature verified when cosign is installed, Glance multihash compared with the index).
- Role `openimages.cloud.oic_sync`: install the oic-sync package and enable its timers
  (Proxmox VE, OpenStack); installs oic-sync 0.4.0 by default.
- Role `openimages.cloud.oic_mirror`: an internal mirror of the catalog with `oic-sync mirror`
  (system user, mirror directory, hardened service and daily timer, optional nginx server
  block), to a local directory or an S3 bucket (`oic_mirror_s3_endpoint_url`, credentials in
  `oic_mirror_s3_environment`, staging directory; needs oic-sync 0.3.0 or newer). Role `oic_sync`: new `oic_sync_configure` (false installs the package only).
- `min_ram` (MiB) from the index on every target (`index_info`) and set as the Glance
  `min_ram` by the role `glance_image` (SCS-0102).
- End of life: `index_info` returns each target's upstream `support` dates (endoflife.date,
  from the index) and its `eol` option (`warn`, `skip`, `fail`) warns about, leaves out or
  refuses images past their end of life; role variable `glance_image_eol`.
