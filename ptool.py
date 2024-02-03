#!/usr/bin/env python3

import argparse
import os
import pyexiv2
from collections import defaultdict


def upto60(x: str) -> str:
    """shortens string to 60 characters"""
    return x if len(x) < 60 else "…%s" % x[-59:]


# TODO: some stuff
class Photo:
    def __init__(self, path: str):
        self.r = pyexiv2.ImageMetadata(path)
        self.r.read()

    def get(self, key: str, default=None):
        return self.r[key].value if key in self.r else default

    @property
    def exif_keys(self):
        return self.r.exif_keys


class BasicProcessor:
    def __init__(self, root: str, exclude: list[str]):
        self.root = root
        for path, dirs, files in os.walk(root):
            for f in files:
                ff = os.path.join(path, f)
                if any(x in ff for x in exclude):
                    continue
                if self.sieve(ff):
                    self.process(ff)

    def sieve(self, filename):
        return filename.endswith(".jpg")


class Cams(BasicProcessor):
    """Collects camera maker / model stats"""

    stat = defaultdict(lambda: defaultdict(int))

    def process(self, f):
        p = Photo(f)
        maker = p.get("Exif.Image.Make", "<UNDEF>").strip()
        model = p.get("Exif.Image.Model", "<UNDEF>").strip()
        self.stat[maker][model] += 1

    def __str__(self):
        r = ""
        for maker in sorted(self.stat.keys()):
            for model in sorted(self.stat[maker].keys()):
                r += f"{maker: >25} | {model: >40} | {self.stat[maker][model]:<5}\n"
        return r


class NoCam(BasicProcessor):
    """Finds photos w/o camera maker/model"""

    lst = []

    def process(self, f):
        p = Photo(f)
        if p.get("Exif.Image.Make") is None or p.get("Exif.Image.Model") is None:
            self.lst.append(f)

    def __str__(self):
        return "\n".join(self.lst)


class Hugin(BasicProcessor):
    """Finds Hugin-processed photos"""

    lst = {}

    def process(self, f):
        p = Photo(f)
        software = p.get("Exif.Image.Software", "")
        if "Hugin" in software:
            self.lst[f] = software

    def __str__(self):
        return "\n".join(f"{upto60(k): >60} | {v: <30}" for k, v in self.lst.items())


class NoGPS(BasicProcessor):
    """Find photos without GPS tag"""

    lst = []

    def process(self, f):
        p = Photo(f)
        if (
            p.get("Exif.GPSInfo.GPSLatitude") is None
            or p.get("Exif.GPSInfo.GPSLongitude") is None
        ):
            self.lst.append(f)

    def __str__(self):
        return "\n".join(self.lst)


class NoGPSDir(BasicProcessor):
    lst = {}

    def process(self, f):
        p = Photo(f)
        nogps = (
            p.get("Exif.GPSInfo.GPSLatitude") is None
            or p.get("Exif.GPSInfo.GPSLongitude") is None
        )
        dirname = os.path.dirname(f).removeprefix(self.root)
        self.lst.setdefault(dirname, {True: 0, False: 0})
        self.lst[dirname][nogps] += 1

    def __str__(self):
        return "\n".join(
            f"{v[True]:3} / {v[False]:<3} {k}"
            for k, v in sorted(self.lst.items(), key=lambda x: x[1][True])
            if v[True] > 0
        )


class SameTag(BasicProcessor):
    tags = {}

    def process(self, f):
        p = Photo(f)
        for key in p.exif_keys:
            val = str(p.get(key))
            if key not in self.tags:
                self.tags[key] = {"c": 1, "v": val}
            else:
                if self.tags[key]["v"] == val:
                    self.tags[key]["c"] += 1
                else:
                    self.tags[key] = {"c": -1, "v": "<DIFFERENT>"}

    def __str__(self):
        return "\n".join(
            f'{y["c"]:5} | {x:40} | {y["v"]}'
            for x, y in sorted(self.tags.items(), key=lambda x: x[1]["c"])
        )


_parser = argparse.ArgumentParser()
_parser.add_argument(
    "mode",
    action="store",
    type=str,
    choices=("cams", "nocam", "hugin", "nogps", "nogpsdir", "sametag"),
)
_parser.add_argument("root", action="store", type=str)
_parser.add_argument("-x", "--exclude", action="append", type=str, default=[])

if __name__ == "__main__":
    args = _parser.parse_args()
    modes = {
        "cams": Cams,
        "nocam": NoCam,
        "hugin": Hugin,
        "nogps": NoGPS,
        "nogpsdir": NoGPSDir,
        "sametag": SameTag,
    }
    print(modes[args.mode](root=args.root, exclude=args.exclude))
