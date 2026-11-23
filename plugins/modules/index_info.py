#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: Contributors to the openimages.cloud project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: index_info
short_description: Read the openimages.cloud catalog index and select images
description:
  - Fetches the catalog index of openimages.cloud (schema C(oic-index/v1)) and returns the
    artifacts to import, with their URL, digests, size, stable name and complete Glance
    property set.
  - Names and properties follow the rules of oic-sync, so that both tools create and
    recognise the same images.
  - Makes no change anywhere.
version_added: "0.1.0"
author:
  - Kevin Allioli (@kallioli)
options:
  index_url:
    description:
      - URL of the catalog index. Change it to use a mirror.
    type: str
    default: https://images.openimages.cloud/index.json
  images:
    description:
      - Image ids to select, for example C(debian-13).
      - When empty, every image except the service images (C(octavia-amphora),
        C(manila-service-image), C(trove-guest-image)), C(cirros) and C(cloud-rescue).
      - An id the index does not list is an error.
    type: list
    elements: str
    default: []
  variants:
    description:
      - 'Variants to keep for multi-variant images, by image id, for example
        C({"alpine-linux": ["uefi"]}). Images not named keep every variant.'
    type: dict
    default: {}
  architecture:
    description:
      - Artifact architecture to select.
    type: str
    default: x86_64
  properties:
    description:
      - Extra or overriding Glance properties added to every artifact.
      - The C(oic_*) keys are reserved.
    type: dict
    default: {}
  with_optional_properties:
    description:
      - Add the optional Glance properties of the catalog (C(hw_rng_model=virtio)). Flavors
        must then allow C(hw_rng:allowed=True).
    type: bool
    default: false
  name_prefix:
    description:
      - Prefix added to every image name.
    type: str
    default: ""
  names:
    description:
      - Image names by artifact key (C(debian-13), C(alpine-linux/uefi)), replacing the
        stable name and the prefix.
    type: dict
    default: {}
  eol:
    description:
      - Images whose upstream release is past its end of life (U(https://endoflife.date)
        dates published in the index).
      - C(warn) returns them with a warning, C(skip) leaves them out, C(fail) fails the task.
      - Within six months of the end of life, a warning only.
    type: str
    choices: [warn, skip, fail]
    default: warn
    version_added: "0.1.0"
  timeout:
    description:
      - HTTP timeout in seconds.
    type: int
    default: 30
  validate_certs:
    description:
      - Verify the TLS certificate of the index server.
    type: bool
    default: true
  http_agent:
    description:
      - User-Agent header sent to the catalog.
    type: str
    default: ansible-httpget
attributes:
  check_mode:
    description: Can run in check mode and return changed status prediction without modifying target.
    support: full
  diff_mode:
    description: Will return details on what has changed (or possibly needs changing in check mode), when in diff mode.
    support: none
"""

EXAMPLES = r"""
- name: Select Debian 13 and the UEFI variant of Alpine Linux
  openimages.cloud.index_info:
    images: [debian-13, alpine-linux]
    variants:
      alpine-linux: [uefi]
  register: oic

- name: Show what would be imported
  ansible.builtin.debug:
    msg: "{{ oic.targets | map(attribute='key') | list }}"
"""

RETURN = r"""
schema:
  description: Schema of the index.
  returned: success
  type: str
  sample: oic-index/v1
generated_at:
  description: Generation time of the index.
  returned: success
  type: str
  sample: "2026-11-16T16:02:27Z"
signing:
  description: Signing section of the index (cosign keyless identity and issuer).
  returned: success
  type: dict
  sample:
    type: cosign-keyless
    bundle_format: sigstore-bundle
    certificate_identity_regexp: "^https://github.com/open-img-cloud/..."
    certificate_oidc_issuer: https://token.actions.githubusercontent.com
targets:
  description: Selected artifacts.
  returned: success
  type: list
  elements: dict
  contains:
    key:
      description: Artifact key, the image id plus C(/variant) for variants.
      type: str
      sample: alpine-linux/uefi
    image_id:
      description: Catalog image id (Glance property C(oic_id)).
      type: str
      sample: alpine-linux
    variant:
      description: Variant, or null.
      type: str
      sample: uefi
    stable_name:
      description: Name oic-sync gives the newest version.
      type: str
      sample: Alpine Linux (UEFI)
    name:
      description: Name to give the image (stable name with the prefix, or the override).
      type: str
      sample: Alpine Linux (UEFI)
    version:
      description: Catalog version (Glance property C(oic_version)).
      type: str
      sample: 3.24.1
    url:
      description: Versioned URL of the qcow2.
      type: str
    bundle_url:
      description: URL of the cosign (Sigstore) bundle of the qcow2.
      type: str
    sha256:
      description: sha256 of the qcow2, covered by the signature.
      type: str
    sha512:
      description: sha512 of the qcow2, or null.
      type: str
    size:
      description: Size of the qcow2 in bytes.
      type: int
    min_disk:
      description: Virtual size rounded up to GiB, or null.
      type: int
    min_ram:
      description: Smallest RAM the image boots with, in MiB (Glance min_ram), or null with an older index.
      type: int
    format:
      description: Disk format.
      type: str
      sample: qcow2
    properties:
      description: Complete Glance property set, C(oic_*) keys included.
      type: dict
    support:
      description:
        - Upstream support of the image's release, from U(https://endoflife.date) at catalog
          build time, or null when the catalog has none.
      type: dict
      contains:
        release:
          description: Upstream release.
          type: str
          sample: "13"
        security_until:
          description: End of life (end of security support), ISO date.
          type: str
          sample: "2030-06-30"
        is_eol:
          description: The end of life is past.
          type: bool
        eol_soon:
          description: The end of life is within six months.
          type: bool
        source:
          description: endoflife.date page of the product.
          type: str
"""

import json

from ansible.module_utils.basic import AnsibleModule
from ansible.module_utils.common.text.converters import to_native
from ansible.module_utils.urls import open_url

from ansible_collections.openimages.cloud.plugins.module_utils.oic_index import (
    DEFAULT_INDEX_URL,
    MAX_INDEX_BYTES,
    OicIndexError,
    apply_eol_policy,
    select_targets,
)


def fetch_index(module):
    url = module.params["index_url"]
    try:
        response = open_url(
            url,
            timeout=module.params["timeout"],
            validate_certs=module.params["validate_certs"],
            http_agent=module.params["http_agent"],
            headers={"Accept": "application/json"},
        )
        body = response.read(MAX_INDEX_BYTES + 1)
    except Exception as e:
        module.fail_json(msg="cannot fetch the index %s: %s" % (url, to_native(e)))
    if len(body) > MAX_INDEX_BYTES:
        module.fail_json(msg="the index %s is larger than %d bytes" % (url, MAX_INDEX_BYTES))
    try:
        return json.loads(body)
    except ValueError as e:
        module.fail_json(msg="the index %s is not valid JSON: %s" % (url, to_native(e)))


def main():
    module = AnsibleModule(
        argument_spec=dict(
            index_url=dict(type="str", default=DEFAULT_INDEX_URL),
            images=dict(type="list", elements="str", default=[]),
            variants=dict(type="dict", default={}),
            architecture=dict(type="str", default="x86_64"),
            properties=dict(type="dict", default={}),
            with_optional_properties=dict(type="bool", default=False),
            name_prefix=dict(type="str", default=""),
            names=dict(type="dict", default={}),
            timeout=dict(type="int", default=30),
            validate_certs=dict(type="bool", default=True),
            http_agent=dict(type="str", default="ansible-httpget"),
            eol=dict(type="str", default="warn", choices=["warn", "skip", "fail"]),
        ),
        supports_check_mode=True,
    )
    index = fetch_index(module)
    try:
        targets = select_targets(
            index,
            images=module.params["images"],
            variants=module.params["variants"],
            architecture=module.params["architecture"],
            extra_properties=module.params["properties"],
            with_optional_properties=module.params["with_optional_properties"],
            name_prefix=module.params["name_prefix"],
            names=module.params["names"],
        )
        targets, warnings = apply_eol_policy(targets, module.params["eol"])
    except OicIndexError as e:
        module.fail_json(msg=to_native(e))
    for warning in warnings:
        module.warn(warning)
    if not targets:
        module.fail_json(msg="no artifact matches the selection")
    module.exit_json(
        changed=False,
        schema=index.get("schema"),
        generated_at=index.get("generated_at"),
        signing=index.get("signing") or {},
        targets=targets,
    )


if __name__ == "__main__":
    main()
