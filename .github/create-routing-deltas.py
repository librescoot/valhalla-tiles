#!/usr/bin/env python3
"""Generate verified HDiff patches from the latest published base per region."""
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

TAR = re.compile(r"^valhalla_tiles_([a-z0-9_-]+)\.tar$")
TAG = re.compile(r"^tiles-[A-Za-z0-9]+$")


def bases(releases):
    result = {}
    ordered = sorted(releases, key=lambda r: r.get("published_at") or "", reverse=True)
    for release in ordered:
        tag = release.get("tag_name", "")
        if release.get("draft") or release.get("prerelease") or not TAG.fullmatch(tag):
            continue
        for asset in release.get("assets", []):
            match = TAR.fullmatch(asset["name"])
            digest = asset.get("digest") or ""
            if match and match.group(1) not in result and re.fullmatch(r"sha256:[0-9a-f]{64}", digest):
                result[match.group(1)] = (tag, asset)
    return result


def sha256(path):
    with path.open("rb") as f:
        return hashlib.file_digest(f, "sha256").hexdigest()


def main():
    artifacts = Path(sys.argv[1])
    pages = json.loads(subprocess.check_output(
        ["gh", "api", "--paginate", "--slurp", "repos/librescoot/valhalla-tiles/releases?per_page=100"]))
    previous = bases([release for page in pages for release in page])
    for target in sorted(artifacts.glob("**/valhalla_tiles_*.tar")):
        match = TAR.fullmatch(target.name)
        if not match or match.group(1) not in previous:
            continue
        region = match.group(1)
        tag, asset = previous[region]
        compressed = target.with_name(target.name + ".zst")
        if not compressed.is_file():
            raise RuntimeError(f"missing compressed target: {compressed}")
        output = target.with_name(f"valhalla_tiles_{region}.from-{tag}.hdelta")
        with tempfile.TemporaryDirectory(prefix="routing-delta-") as tmp:
            subprocess.run(["gh", "release", "download", tag, "--repo", "librescoot/valhalla-tiles",
                            "--pattern", target.name, "--dir", tmp], check=True)
            base = Path(tmp) / target.name
            if base.stat().st_size != asset["size"] or sha256(base) != asset["digest"][7:]:
                raise RuntimeError(f"base release verification failed: {tag}/{target.name}")
            subprocess.run(["hdiffz", "-m-4", "-p-2", "-c-zstd-20", str(base), str(target), str(output)], check=True)
            subprocess.run(["hdiffz", "-t", str(base), str(target), str(output)], check=True)
        if output.stat().st_size >= compressed.stat().st_size:
            output.unlink()
            print(f"{region}: full compressed archive is smaller", flush=True)
        else:
            print(f"{region}: {tag} -> {output.name}, {output.stat().st_size} bytes", flush=True)


if __name__ == "__main__":
    main()
