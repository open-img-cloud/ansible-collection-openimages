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
    apply_eol_policy,
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


def _eol_index(is_eol=True, eol_soon=False):
    idx = index()
    debian = [i for i in idx["images"] if i["id"] == "debian-13"][0]
    debian["support"] = {
        "release": "13",
        "security_until": "2026-06-30",
        "is_eol": is_eol,
        "eol_soon": eol_soon,
        "source": "https://endoflife.date/debian",
    }
    return idx


def test_support_is_returned():
    targets = select_targets(_eol_index(), images=["debian-13"])
    assert targets[0]["support"]["security_until"] == "2026-06-30"


def test_eol_warn_keeps_the_image():
    targets, warnings = apply_eol_policy(select_targets(_eol_index(), images=["debian-13"]), "warn")
    assert [t["image_id"] for t in targets] == ["debian-13"]
    assert warnings == [
        "debian-13: release 13 reached its upstream end of life on 2026-06-30 (imported anyway)"
    ]


def test_eol_skip_leaves_it_out():
    targets = apply_eol_policy(select_targets(_eol_index()), "skip")[0]
    assert "debian-13" not in [t["image_id"] for t in targets]


def test_eol_fail_refuses():
    with pytest.raises(OicIndexError, match="past their upstream end of life: debian-13"):
        apply_eol_policy(select_targets(_eol_index()), "fail")


def test_eol_soon_only_warns():
    targets, warnings = apply_eol_policy(select_targets(_eol_index(False, True)), "fail")
    assert "debian-13" in [t["image_id"] for t in targets]
    assert len(warnings) == 1


def test_malformed_support_is_ignored():
    idx = index()
    idx["images"][0]["support"] = "soon"
    targets, warnings = apply_eol_policy(select_targets(idx, images=[idx["images"][0]["id"]]), "fail")
    assert targets[0]["support"] is None
    assert warnings == []
