# -*- coding: utf-8 -*-
# Copyright: Contributors to the openimages.cloud project
# GNU General Public License v3.0+ (see LICENSE or https://www.gnu.org/licenses/gpl-3.0.txt)

"""Parsing and selection of the openimages.cloud catalog index (schema oic-index/v1).

Mirrors the rules of oic-sync (oic_sync/index.py) so that both tools create the same images:
stable names ("Debian 13", "Alpine Linux (UEFI)"), property precedence and the oic_* keys.
"""

from __future__ import absolute_import, division, print_function

__metaclass__ = type

import math

INDEX_SCHEMA = "oic-index/v1"
DEFAULT_INDEX_URL = "https://images.openimages.cloud/index.json"
MAX_INDEX_BYTES = 16 * 1024 * 1024
RESERVED_PROPERTIES = ("oic_id", "oic_variant", "oic_version", "oic_sha256")
# Images oic-sync leaves out unless named: OpenStack service images, the test and rescue images.
SERVICE_IMAGES = ("octavia-amphora", "manila-service-image", "trove-guest-image", "cirros", "cloud-rescue")


class OicIndexError(ValueError):
    """The index is invalid or does not hold what was asked."""


def check_index(index):
    if not isinstance(index, dict):
        raise OicIndexError("the index is not a JSON object")
    if index.get("schema") != INDEX_SCHEMA:
        raise OicIndexError("unsupported index schema %r (expected %s)" % (index.get("schema"), INDEX_SCHEMA))
    if not isinstance(index.get("images"), list):
        raise OicIndexError("the index has no images list")
    return index


def stable_name(image, artifact):
    """Name held by the newest version, as in oic-sync: the title, plus the variant when there are several."""
    title = image.get("title") or image["id"]
    if artifact.get("variant") and len(image.get("artifacts") or []) > 1:
        return "%s (%s)" % (title, artifact["variant"].upper())
    return title


def artifact_key(image_id, variant):
    return "%s/%s" % (image_id, variant) if variant else image_id


def min_disk_gib(virtual_size):
    if not virtual_size:
        return None
    return int(math.ceil(virtual_size / float(2 ** 30)))


def glance_properties(image, artifact, extra_properties=None, with_optional=False):
    """Properties for one artifact: optional set, index set, extra properties, then oic_* keys."""
    props = {}
    if with_optional:
        props.update(image.get("optional_glance_properties") or {})
    props.update(artifact.get("glance_properties") or {})
    props.update(extra_properties or {})
    props["oic_id"] = image["id"]
    props["oic_version"] = artifact["version"]
    props["oic_sha256"] = artifact["sha256"].lower()
    if artifact.get("variant"):
        props["oic_variant"] = artifact["variant"]
    return dict((str(k), str(v)) for k, v in props.items())


EOL_POLICIES = ("warn", "skip", "fail")


def support_of(image):
    """Upstream support of the image's release (endoflife.date, published in the index), or None.

    Informational: a malformed block is ignored rather than failing the selection.
    """
    raw = image.get("support")
    if not isinstance(raw, dict) or not isinstance(raw.get("release"), str):
        return None
    until = raw.get("security_until")
    is_eol = raw.get("is_eol") is True
    return {
        "release": raw["release"],
        "security_until": until if isinstance(until, str) else None,
        "is_eol": is_eol,
        "eol_soon": raw.get("eol_soon") is True and not is_eol,
        "source": raw.get("source") if isinstance(raw.get("source"), str) else None,
    }


def eol_message(image_id, support):
    when = support["security_until"] or "an unknown date"
    verb = "reached its upstream end of life on" if support["is_eol"] else "reaches its upstream end of life on"
    return "%s: release %s %s %s" % (image_id, support["release"], verb, when)


def apply_eol_policy(targets, policy="warn"):
    """(targets, warnings): drop (skip) or refuse (fail) targets past their end of life."""
    if policy not in EOL_POLICIES:
        raise OicIndexError("eol must be one of %s" % ", ".join(EOL_POLICIES))
    warnings = []
    eol = []
    seen = set()
    for t in targets:
        s = t.get("support")
        if not s or not (s["is_eol"] or s["eol_soon"]) or t["image_id"] in seen:
            continue
        seen.add(t["image_id"])
        if s["is_eol"]:
            eol.append(t["image_id"])
            action = {"warn": "imported anyway", "skip": "skipped", "fail": "refused"}[policy]
        else:
            action = "plan the move to a newer release"
        warnings.append("%s (%s)" % (eol_message(t["image_id"], s), action))
    if eol and policy == "fail":
        raise OicIndexError(
            "image(s) past their upstream end of life: %s (eol=warn to import them anyway, "
            "eol=skip to leave them out)" % ", ".join(eol)
        )
    if policy == "skip":
        targets = [t for t in targets if t["image_id"] not in eol]
    return targets, warnings


def select_targets(
    index,
    images=None,
    variants=None,
    architecture="x86_64",
    extra_properties=None,
    with_optional_properties=False,
    name_prefix="",
    names=None,
):
    """Artifacts to import, with everything a Glance import needs.

    images: ids to keep (every non-service image when empty); an unknown id is an error.
    variants: dict image id -> list of variants; images not named keep every variant.
    """
    check_index(index)
    reserved = sorted(set(RESERVED_PROPERTIES).intersection(extra_properties or {}))
    if reserved:
        raise OicIndexError("properties reserved to openimages.cloud tools: %s" % ", ".join(reserved))
    by_id = dict((img.get("id"), img) for img in index["images"] if isinstance(img, dict))
    wanted = []
    for image_id in images or []:
        if image_id not in wanted:
            wanted.append(image_id)
    unknown = [i for i in wanted if i not in by_id]
    if unknown:
        raise OicIndexError(
            "unknown image id(s): %s (the index lists: %s)" % (", ".join(unknown), ", ".join(sorted(by_id)))
        )
    variants = variants or {}
    names = names or {}
    ids = wanted or [i for i in by_id if i not in SERVICE_IMAGES]
    targets = []
    for image_id in ids:
        image = by_id[image_id]
        for artifact in image.get("artifacts") or []:
            variant = artifact.get("variant")
            if artifact.get("arch") != architecture:
                continue
            if variant and image_id in variants and variant not in variants[image_id]:
                continue
            for field in ("version", "url", "sha256"):
                if not artifact.get(field):
                    raise OicIndexError("%s: artifact without %s" % (image_id, field))
            key = artifact_key(image_id, variant)
            stable = stable_name(image, artifact)
            targets.append(
                {
                    "key": key,
                    "image_id": image_id,
                    "variant": variant,
                    "title": image.get("title") or image_id,
                    "stable_name": stable,
                    "name": names.get(key, "%s%s" % (name_prefix or "", stable)),
                    "version": artifact["version"],
                    "url": artifact["url"],
                    "bundle_url": artifact.get("bundle_url"),
                    "signed": bool(artifact.get("signed")),
                    "sha256": artifact["sha256"].lower(),
                    "sha512": (artifact.get("sha512") or "").lower() or None,
                    "size": artifact.get("size"),
                    "virtual_size": artifact.get("virtual_size"),
                    "min_disk": min_disk_gib(artifact.get("virtual_size")),
                    # Glance min_ram in MiB (index field since 2026-11, SCS-0102), or None.
                    "min_ram": image.get("min_ram"),
                    "format": artifact.get("format") or "qcow2",
                    "firmware": artifact.get("firmware"),
                    "arch": artifact.get("arch"),
                    "login_user": image.get("login_user"),
                    "support": support_of(image),
                    "properties": glance_properties(image, artifact, extra_properties, with_optional_properties),
                }
            )
    return targets
