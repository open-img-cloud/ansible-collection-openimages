#!/usr/bin/python
# -*- coding: utf-8 -*-
# Copyright: Contributors to the openimages.cloud project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

DOCUMENTATION = r"""
---
module: glance_info
short_description: Find the openimages.cloud images of the current project in Glance
description:
  - Lists the Glance images of the current project that carry an C(oic_id) property, hidden
    images included, with the C(oic_*) properties and the multihash Glance computed.
  - These are the images that oic-sync and the C(openimages.cloud.glance_image) role manage.
    Images of other projects (public images of the operator, for example) are left out.
  - Also returns the image import methods the cloud offers.
  - Uses server-side property filters of the Glance v2 API, like oic-sync.
version_added: "0.1.0"
author:
  - Kevin Allioli (@kallioli)
options:
  oic_ids:
    description:
      - Catalog image ids to look for (values of the C(oic_id) property).
    type: list
    elements: str
    required: true
extends_documentation_fragment:
  - openstack.cloud.openstack
attributes:
  check_mode:
    description: Can run in check mode and return changed status prediction without modifying target.
    support: full
  diff_mode:
    description: Will return details on what has changed (or possibly needs changing in check mode), when in diff mode.
    support: none
"""

EXAMPLES = r"""
- name: Find the Debian 13 images of the project
  openimages.cloud.glance_info:
    cloud: mycloud
    oic_ids: [debian-13]
  register: found

- name: Versions present
  ansible.builtin.debug:
    msg: "{{ found.images | map(attribute='oic_version') | list }}"
"""

RETURN = r"""
project_id:
  description: Current project (owner of the images returned).
  returned: success
  type: str
import_methods:
  description: Image import methods the cloud offers (C(GET /v2/info/import)), empty when unknown.
  returned: success
  type: list
  elements: str
  sample: [glance-direct, web-download]
images:
  description: Images of the current project with one of the requested C(oic_id) values.
  returned: success
  type: list
  elements: dict
  contains:
    id:
      description: Image UUID.
      type: str
    name:
      description: Image name.
      type: str
    status:
      description: Glance status (C(active), C(queued), C(importing), C(killed)...).
      type: str
    visibility:
      description: Visibility.
      type: str
    hidden:
      description: Value of C(os_hidden).
      type: bool
    created_at:
      description: Creation time.
      type: str
    size:
      description: Size in bytes.
      type: int
    hash_algo:
      description: Algorithm of the multihash Glance computed (C(os_hash_algo)).
      type: str
    hash_value:
      description: Multihash Glance computed (C(os_hash_value)).
      type: str
    oic_id:
      description: Catalog image id.
      type: str
    oic_variant:
      description: Variant, or null.
      type: str
    oic_version:
      description: Catalog version.
      type: str
    oic_sha256:
      description: sha256 of the imported qcow2 according to the index.
      type: str
"""

from ansible_collections.openstack.cloud.plugins.module_utils.openstack import OpenStackModule

PAGE = 200


class GlanceInfoModule(OpenStackModule):
    argument_spec = dict(
        oic_ids=dict(type="list", elements="str", required=True),
    )
    module_kwargs = dict(supports_check_mode=True)

    def _get(self, path, params=None):
        response = self.conn.image.get(path, params=params)
        if response.status_code != 200:
            self.fail_json(msg="GET %s: HTTP %s %s" % (path, response.status_code, (response.text or "")[:300]))
        return response.json()

    def _import_methods(self):
        response = self.conn.image.get("/info/import")
        if response.status_code != 200:
            return []
        return list(response.json().get("import-methods", {}).get("value", []))

    def _list(self, filters):
        images = []
        params = dict(filters, limit=PAGE)
        while True:
            body = self._get("/images", params=params)
            page = body.get("images", [])
            images.extend(page)
            if not page or not body.get("next"):
                return images
            params = dict(params, marker=page[-1]["id"])

    def run(self):
        project_id = self.conn.current_project_id
        if not project_id:
            self.fail_json(msg="cannot determine the current project (a project-scoped token is required)")
        found = {}
        for oic_id in self.params["oic_ids"]:
            base = {"oic_id": oic_id, "owner": project_id}
            # Hidden images are left out of the default list: query both.
            for extra in ({}, {"os_hidden": "true"}):
                for img in self._list(dict(base, **extra)):
                    # Filters are exact server side; check again in case a proxy ignored them.
                    if img.get("oic_id") == oic_id and img.get("owner") in (None, project_id):
                        found[img["id"]] = img
        images = [
            dict(
                id=img["id"],
                name=img.get("name"),
                status=img.get("status"),
                visibility=img.get("visibility"),
                hidden=bool(img.get("os_hidden", False)),
                created_at=img.get("created_at"),
                size=img.get("size"),
                hash_algo=img.get("os_hash_algo"),
                hash_value=img.get("os_hash_value"),
                oic_id=img.get("oic_id"),
                oic_variant=img.get("oic_variant") or None,
                oic_version=img.get("oic_version"),
                oic_sha256=(img.get("oic_sha256") or "").lower() or None,
            )
            for img in sorted(found.values(), key=lambda i: i.get("created_at") or "")
        ]
        self.exit_json(
            changed=False,
            project_id=project_id,
            import_methods=self._import_methods(),
            images=images,
        )


def main():
    module = GlanceInfoModule()
    module()


if __name__ == "__main__":
    main()
