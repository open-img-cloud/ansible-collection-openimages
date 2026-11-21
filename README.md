<p align="center">
  <a href="https://openimages.cloud">
    <img src="https://openimages.cloud/img/og.png" alt="openimages.cloud: signed, boot-tested cloud images for OpenStack and Proxmox" width="720">
  </a>
</p>

<h1 align="center">openimages.cloud Ansible collection</h1>

<p align="center">
  <a href="https://github.com/open-img-cloud/ansible-collection-openimages/actions/workflows/ci.yml"><img alt="CI" src="https://github.com/open-img-cloud/ansible-collection-openimages/actions/workflows/ci.yml/badge.svg"></a>
  <a href="https://openimages.cloud/verify/"><img alt="Verifies Sigstore cosign signatures" src="https://img.shields.io/badge/verifies-Sigstore%20cosign-2459c4"></a>
  <a href="LICENSE"><img alt="License GPL-3.0-or-later" src="https://img.shields.io/badge/license-GPL--3.0--or--later-555"></a>
</p>

<p align="center">
  <a href="https://openimages.cloud"><b>Website</b></a> ·
  <a href="https://openimages.cloud/images/">Catalog</a> ·
  <a href="https://images.openimages.cloud/index.json">index.json</a> ·
  <a href="https://github.com/open-img-cloud/oic-sync">oic-sync</a> ·
  <a href="https://github.com/open-img-cloud/ansible-collection-openimages/issues">Report an issue</a>
</p>

The `openimages.cloud` collection brings the signed, boot-tested cloud images of
[openimages.cloud](https://openimages.cloud) to OpenStack and Proxmox VE from Ansible.

| Content | What it does |
|---|---|
| role `openimages.cloud.glance_image` | Imports images into OpenStack Glance: sha256 checked, cosign signature verified when cosign is installed, Glance properties of the index, stable names |
| role `openimages.cloud.oic_sync` | Installs [oic-sync](https://github.com/open-img-cloud/oic-sync) from its signed packages and enables its daily timer, on a Proxmox VE node or any Debian/EL host for OpenStack |
| role `openimages.cloud.oic_mirror` | Runs an internal mirror of the catalog with `oic-sync mirror`: signed images copied to a local directory (optionally served by nginx) or an S3 bucket, refreshed daily |
| module `openimages.cloud.index_info` | Reads the catalog index (`oic-index/v1`) and returns the selected artifacts: URL, digests, names, Glance properties |
| module `openimages.cloud.glance_info` | Finds the openimages.cloud images of the current project in Glance (`oic_id` property, hidden images included) |

Status: alpha. The modules, the `oic_sync` role (Debian 13 with systemd) and the cosign
checks were run locally; the `glance_image` role has not been run against a real cloud yet.

## Which tool?

- **Proxmox VE**: the `oic_sync` role. oic-sync keeps one VM template per version, verifies
  signatures and rotates old templates; the role installs it and its timer.
- **OpenStack, images that follow the catalog every day**: oic-sync too (the `oic_sync` role
  on any Debian 12/13 or EL9/EL10 host, or its container image). It also hides retired
  versions and deletes the ones no server or volume uses.
- **No access to the CDN from the clouds** (internal or air-gapped): the `oic_mirror` role on
  a host that can reach it, then point oic-sync, Glance and Proxmox VE at the mirror.
- **OpenStack, images created as part of a playbook** (a tenant bootstrap, a lab, CI): the
  `glance_image` role. It imports what is missing and renames older versions, nothing more.

Both use the same Glance properties and names: images imported by the role are recognised by
oic-sync later, and the reverse.

## Install

```sh
ansible-galaxy collection install openimages.cloud
# before the Galaxy release, from git:
ansible-galaxy collection install git+https://github.com/open-img-cloud/ansible-collection-openimages.git
```

Requirements:

- ansible-core 2.15 or newer (tested with 2.21);
- for `glance_image` and `glance_info`: the `openstack.cloud` collection 2.5.0 or newer (a
  dependency, installed with this collection; checked against 2.7.0) and `openstacksdk` on the
  host that runs them (`pip install openstacksdk`);
- optional: [cosign](https://docs.sigstore.dev/cosign/system_config/installation/) 2.4 or newer
  on that host, for signature verification.

## Import images into Glance

```yaml
- name: Import openimages.cloud images
  hosts: localhost
  connection: local
  gather_facts: false
  roles:
    - role: openimages.cloud.glance_image
      vars:
        glance_image_cloud: mycloud          # clouds.yaml entry; empty uses OS_* variables
        glance_image_images: [debian-13, ubuntu-24.04, alpine-linux]
        glance_image_variants:
          alpine-linux: [uefi]
  post_tasks:
    - name: Use the image ids
      ansible.builtin.debug:
        var: glance_image_ids    # {"debian-13": "<uuid>", "alpine-linux/uefi": "<uuid>", ...}
```

What the role does:

1. **Read the index** (`index_info`) and select the artifacts: one per image, one per variant for
   the multi-variant images (`glance_image_variants` narrows them).
2. **Find** the images of the current project carrying `oic_id` (`glance_info`). A version
   whose `oic_sha256` is already there, active, is not imported again.
3. **Download** each missing qcow2 to a temporary directory, with `get_url` checking the sha256
   of the index.
4. **Verify the signature** when `cosign` is found (or fail when
   `glance_image_verify_signature: required`): `cosign verify-blob` with the bundle of the
   artifact, the signer identity regexp and the OIDC issuer of the index `signing` section (or
   your own, `glance_image_certificate_identity_regexp`).
5. **Upload** with `openstack.cloud.image` under a temporary name ("Debian 13
   (13-20261111-2659, 6706a0cddad2)"), with `min_disk` from the virtual size and every Glance
   property of the index plus `oic_id`, `oic_version`, `oic_sha256` (and `oic_variant`).
6. **Compare** what Glance stored with the index: size, and the multihash Glance computed
   (`os_hash_algo`/`os_hash_value`, sha512 by default). On any failure, the new image is
   deleted.
7. **Rename**: older versions that held the name become "Debian 13 (13-20261103-2651)", the new
   version takes the stable name "Debian 13" (the names oic-sync uses).

Nothing is ever deleted, older versions are not hidden (`openstack.cloud.image` cannot set
`os_hidden`) and the role does not check whether servers use them: for rotation, use oic-sync.

| Variable | Default | Meaning |
|---|---|---|
| `glance_image_images` | (required) | catalog image ids |
| `glance_image_variants` | `{}` | variants to keep, by image id (`{alpine-linux: [uefi]}`) |
| `glance_image_cloud`, `glance_image_region_name` | `""` | clouds.yaml entry (or auth dict) and region |
| `glance_image_visibility` | `private` | `private`, `shared`, `community` or `public` |
| `glance_image_properties` | `{}` | extra or overriding Glance properties (`oic_*` reserved) |
| `glance_image_with_optional_properties` | `false` | add `hw_rng_model=virtio` (flavors must allow `hw_rng:allowed=True`) |
| `glance_image_tags` | `[]` | Glance tags of new images |
| `glance_image_name_prefix`, `glance_image_names` | `""`, `{}` | name prefix, or names by artifact key |
| `glance_image_import_method` | `upload` | `upload` or `web-download` (see below) |
| `glance_image_verify_signature` | `auto` | `auto` (when cosign is found), `required` or `never` |
| `glance_image_require_glance_hash` | `true` | fail when Glance reports no sha256/sha512 multihash |
| `glance_image_retire` | `true` | rename older versions so that only the newest holds the name |
| `glance_image_download_dir` | `""` | download directory (system temporary directory); about 1.3 GB at most per image |
| `glance_image_index_url` | public index | another index, e.g. a mirror |
| `glance_image_eol` | `warn` | images past their upstream end of life ([endoflife.date](https://endoflife.date) dates of the index): `warn` and import, `skip`, or `fail`; within six months, a warning only |
| `glance_image_timeout` | `3600` | seconds to wait for an upload or an import |

`web-download` lets Glance fetch the image itself: nothing goes through the Ansible host, but
the signature cannot be verified (the role refuses it with `verify_signature: required`) and
only Glance's multihash (sha512, not covered by the signature) is compared with the index.
The cloud must offer the `web-download` import method.

## Install oic-sync (Proxmox VE, OpenStack)

```yaml
- name: Keep openimages.cloud templates on Proxmox VE
  hosts: proxmox
  become: true
  roles:
    - role: openimages.cloud.oic_sync
      vars:
        oic_sync_proxmox_images: [debian-13, ubuntu-24.04]
        oic_sync_proxmox_extra_args: --vmid-base 9000 --keep 2 --delete
```

The role downloads the package of the release (`oic-sync_<version>-1.deb12/deb13_amd64.deb`,
`oic-sync-<version>-1.el9/el10.x86_64.rpm`), checks its sha256 against the release
`SHA256SUMS` and, when cosign is installed on the host, its cosign signature (identity: the
`packages.yml` workflow of oic-sync, on a version tag). It installs it, writes
`/etc/default/oic-sync` (Debian, Proxmox VE) or `/etc/sysconfig/oic-sync` (EL) and enables
`oic-sync-proxmox.timer` when images are listed, `oic-sync-openstack.timer` when a cloud and
images are set (both timers run daily).

| Variable | Default | Meaning |
|---|---|---|
| `oic_sync_version` | `0.3.0` | oic-sync release |
| `oic_sync_proxmox_images` | `[]` | images to keep as Proxmox VE templates |
| `oic_sync_proxmox_extra_args` | `""` | other `oic-sync proxmox sync` options |
| `oic_sync_openstack_cloud` | `""` | clouds.yaml entry (`OS_CLOUD`) |
| `oic_sync_openstack_images` | `[]` | images to sync into Glance |
| `oic_sync_openstack_extra_args` | `""` | other `oic-sync openstack sync` options, e.g. `--keep 2` |
| `oic_sync_proxmox_timer`, `oic_sync_openstack_timer` | computed | force a timer on or off |
| `oic_sync_verify_signature` | `auto` | `auto`, `required` or `never` |

Before the first Proxmox VE run, enable the `import` content type on the download storage once
(`pvesm set local --content iso,vztmpl,backup,import`). For OpenStack, the service runs as a
dynamic user: `/etc/openstack/clouds.yaml` must be readable by it.

## Run an internal mirror

```yaml
- name: Mirror openimages.cloud for the internal clouds
  hosts: mirror
  become: true
  roles:
    - role: openimages.cloud.oic_mirror
      vars:
        oic_mirror_base_url: http://mirror.example.net/oic
        oic_mirror_images: [debian-13, ubuntu-24.04, rocky-linux-10]
        oic_mirror_keep: 2
        oic_mirror_prune: true
        oic_mirror_nginx: true
        oic_mirror_nginx_install: true
```

The role installs oic-sync with the `oic_sync` role (package only: an existing Proxmox VE or
OpenStack setup on the host is left alone), creates the `oic-mirror` system user and
`/srv/oic-mirror`, and writes `oic-sync-mirror.service` and its daily timer. The service runs
`oic-sync mirror` as that user, with the filesystem read-only except the mirror directory. Each
run verifies the cosign signature and the digests of every image before it appears in the
mirror, and only downloads what changed (see
[Mirror](https://github.com/open-img-cloud/oic-sync#mirror) in the oic-sync README). The role
runs the mirror once at the end of the play: the first run downloads every selected image.

Then, on the clients: `OIC_INDEX_URL=http://mirror.example.net/oic/index.json`.

| Variable | Default | Meaning |
|---|---|---|
| `oic_mirror_base_url` | required | URL the mirror is served at, written into its `index.json` |
| `oic_mirror_dest` | `/srv/oic-mirror` | mirror directory, or an S3 bucket (`s3://bucket/prefix`) |
| `oic_mirror_images` | `[]` | images to mirror (empty: all except the service images) |
| `oic_mirror_variants` | `[]` | variants to mirror (empty: all) |
| `oic_mirror_include_service_images` | `false` | also the Octavia, Manila and Trove images |
| `oic_mirror_keep` | `1` | versions per image, the latest included |
| `oic_mirror_prune` | `false` | delete versions beyond `oic_mirror_keep` |
| `oic_mirror_eol` | `""` | end of life policy: `warn`, `skip` or `fail` (empty: oic-sync default, `warn`) |
| `oic_mirror_s3_endpoint_url` | `""` | endpoint of an S3-compatible storage (`--s3-endpoint-url`) |
| `oic_mirror_s3_environment` | `{}` | S3 client environment, written to `oic_mirror_env_file` (`/etc/oic-sync/mirror.env`, root:oic-mirror, 0640) |
| `oic_mirror_staging_dir` | `/var/cache/oic-mirror` | S3 only: where each qcow2 is downloaded and verified before upload |
| `oic_mirror_index_url`, `oic_mirror_extra_args` | `""` | another index, other `oic-sync mirror` options |
| `oic_mirror_user`, `oic_mirror_group` | `oic-mirror` | owner of the mirror, user of the service |
| `oic_mirror_timer`, `oic_mirror_on_calendar`, `oic_mirror_randomized_delay` | `true`, `daily`, `1h` | refresh timer |
| `oic_mirror_run_now` | `true` | run the mirror once at the end of the play |
| `oic_mirror_install` | `true` | install oic-sync (`false`: already at `oic_mirror_oic_sync_bin`, `/usr/bin/oic-sync`) |
| `oic_mirror_nginx` | `false` | write `/etc/nginx/conf.d/oic-mirror.conf`, serving the directory at the path of the base URL |
| `oic_mirror_nginx_install` | `false` | also install and start nginx |
| `oic_mirror_nginx_listen`, `oic_mirror_nginx_server_name`, `oic_mirror_nginx_location` | `80`, host and path of the base URL | server block |

### Mirror to an S3 bucket

```yaml
- role: openimages.cloud.oic_mirror
  vars:
    oic_mirror_dest: s3://images/oic
    oic_mirror_base_url: https://s3.example.net/images/oic
    oic_mirror_s3_endpoint_url: https://s3.example.net
    oic_mirror_s3_environment:
      AWS_ACCESS_KEY_ID: "{{ vault_mirror_access_key }}"
      AWS_SECRET_ACCESS_KEY: "{{ vault_mirror_secret_key }}"
      AWS_DEFAULT_REGION: us-east-1
    oic_mirror_keep: 2
    oic_mirror_prune: true
```

The bucket serves the mirror itself: no web server (`oic_mirror_nginx` is refused with an S3
destination). It needs oic-sync 0.3.0 or newer with the `s3` extra: the packages installed by
the role and the container image include it, a pipx install needs `pipx install 'oic-sync[s3]'`.
The S3 client reads the usual AWS settings from `oic_mirror_s3_environment`:
`AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`, `AWS_DEFAULT_REGION`, and `AWS_ENDPOINT_URL` as an
alternative to `oic_mirror_s3_endpoint_url`. They land in `/etc/oic-sync/mirror.env` (readable
by root and the service group only, never logged); keep the secret in Ansible Vault. Each qcow2
is downloaded and verified in `oic_mirror_staging_dir` (the service cache directory by default,
kept between runs so an interrupted download resumes) before it is uploaded: plan 2 GiB free
there. Bucket policies and ACLs are left to you, see
[S3 bucket](https://github.com/open-img-cloud/oic-sync#s3-bucket) in the oic-sync README.

The nginx server block listens on plain HTTP: add TLS yourself or terminate it in front.
Integrity does not depend on it (clients check the signed digests), but HTTPS stops an attacker
on the path from serving an older signed version. `.part` downloads and the lock file are
never served.

## Modules

```yaml
- name: What the index offers (no cloud needed)
  openimages.cloud.index_info:
    images: [debian-13, alpine-linux]
  register: oic

- name: Versions of Debian 13 in the project
  openimages.cloud.glance_info:
    cloud: mycloud
    oic_ids: [debian-13]
  register: found
```

`ansible-doc openimages.cloud.index_info` and `ansible-doc openimages.cloud.glance_info` list
the options and return values. See [`examples/`](examples/).

## Use the images

Look images up by the `oic_id` property, not by name: the name moves to each new version.

```yaml
- name: Current Debian 13 image of the project
  openimages.cloud.glance_info:
    cloud: mycloud
    oic_ids: [debian-13]
  register: found

- name: Boot a server
  openstack.cloud.server:
    cloud: mycloud
    name: web1
    image: "{{ (found.images | selectattr('status', 'equalto', 'active') | last).id }}"
    flavor: m1.small
    network: private
```

## Development

```sh
ansible-lint
ansible-galaxy collection build
# ansible-test needs the collection under ansible_collections/openimages/cloud
ansible-galaxy collection install -p ../.. openstack.cloud
ansible-test sanity --docker default
ansible-test units --docker default
```

## License

GPL-3.0-or-later, the license of ansible-core and of most Ansible collections, including
`openstack.cloud` whose `module_utils` the `glance_info` module imports. Code distributed with
GPL-3.0 modules this way is simplest to keep under the same license; the rest of the
openimages.cloud project stays Apache-2.0.
