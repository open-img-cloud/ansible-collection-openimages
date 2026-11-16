# -*- coding: utf-8 -*-
# Copyright: Contributors to the openimages.cloud project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import copy
import json
import os

import pytest

from ansible_collections.openimages.cloud.plugins.module_utils.oic_index import (
    OicIndexError,
    min_disk_gib,
    select_targets,
)

with open(os.path.join(os.path.dirname(__file__), "fixtures", "index.json")) as f:
    INDEX = json.load(f)


def index():
    return copy.deepcopy(INDEX)


def test_default_selection_leaves_out_service_and_test_images():
    keys = [t["key"] for t in select_targets(index())]
    assert "cirros" not in keys
    assert sorted(keys) == ["alpine-linux/bios", "alpine-linux/uefi", "debian-13"]


def test_named_test_image_is_selected():
    assert [t["key"] for t in select_targets(index(), images=["cirros"])] == ["cirros"]


def test_names_follow_oic_sync():
    targets = {t["key"]: t for t in select_targets(index(), images=["debian-13", "alpine-linux"])}
    assert targets["debian-13"]["name"] == "Debian 13"
    assert targets["alpine-linux/uefi"]["name"] == "Alpine Linux (UEFI)"


def test_variants_filter():
    targets = select_targets(index(), images=["alpine-linux"], variants={"alpine-linux": ["uefi"]})
    assert [t["key"] for t in targets] == ["alpine-linux/uefi"]


def test_properties_precedence_and_oic_keys():
    (debian,) = select_targets(
        index(),
        images=["debian-13"],
        extra_properties={"hw_vif_multiqueue_enabled": "false", "site": "gva"},
        with_optional_properties=True,
    )
    props = debian["properties"]
    assert props["hw_vif_multiqueue_enabled"] == "false"
    assert props["site"] == "gva"
    assert props["hw_rng_model"] == "virtio"
    assert props["oic_id"] == "debian-13"
    assert props["oic_version"] == debian["version"]
    assert props["oic_sha256"] == debian["sha256"]
    assert "oic_variant" not in props
    assert debian["min_disk"] == 3


def test_variant_property_and_firmware():
    (uefi,) = select_targets(index(), images=["alpine-linux"], variants={"alpine-linux": ["uefi"]})
    assert uefi["properties"]["oic_variant"] == "uefi"
    assert uefi["properties"]["hw_firmware_type"] == "uefi"


def test_prefix_and_name_override():
    targets = {
        t["key"]: t
        for t in select_targets(
            index(), images=["debian-13", "alpine-linux"], name_prefix="oic/", names={"alpine-linux/bios": "alpine"}
        )
    }
    assert targets["debian-13"]["name"] == "oic/Debian 13"
    assert targets["alpine-linux/bios"]["name"] == "alpine"


def test_unknown_image_is_an_error():
    with pytest.raises(OicIndexError, match="no-such-image"):
        select_targets(index(), images=["no-such-image"])


def test_reserved_properties_are_refused():
    with pytest.raises(OicIndexError, match="oic_version"):
        select_targets(index(), images=["debian-13"], extra_properties={"oic_version": "1"})


def test_wrong_schema_is_refused():
    data = index()
    data["schema"] = "oic-index/v2"
    with pytest.raises(OicIndexError, match="schema"):
        select_targets(data)


def test_min_disk():
    assert min_disk_gib(None) is None
    assert min_disk_gib(2 ** 30) == 1
    assert min_disk_gib(2 ** 30 + 1) == 2
