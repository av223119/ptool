#!/usr/bin/env python3

import abc
import argparse
import concurrent.futures
import dataclasses
import os
import pyexiv2
from typing import override


def upto60(x: str) -> str:
    """shortens string to 60 characters"""
    return x if len(x) < 60 else "…%s" % x[-59:]


class Photo:
    def __init__(self, path: str):
        self.r = pyexiv2.ImageMetadata(path)
        self.r.read()

    def get(self, key: str, default: str = "") -> str:
        return self.r[key].value if key in self.r else default

    @property
    def exif_keys(self) -> list[str]:
        return self.r.exif_keys


class BasicProcessor[T]:
    def __init__(
        self, root: str, exclude: list[str], executor: concurrent.futures.Executor
    ):
        self.root: str = root
        self.tasks: list[concurrent.futures.Future[T]] = []
        for path, _, files in os.walk(root):
            for f in files:
                ff = os.path.join(path, f)
                if any(x in ff for x in exclude):
                    continue
                if self.sieve(ff):
                    self.tasks.append(executor.submit(self.process, ff))

    @staticmethod
    @abc.abstractmethod
    def process(f: str) -> T: ...

    @staticmethod
    def sieve(fn: str) -> bool:
        return fn.endswith(".jpg")

    @override
    def __str__(self) -> str:
        return ""


class Cams(BasicProcessor[tuple[str, str]]):
    """Collects camera maker / model stats"""

    @override
    @staticmethod
    def process(f: str):
        p = Photo(f)
        maker = p.get("Exif.Image.Make", "<UNDEF>").strip()
        model = p.get("Exif.Image.Model", "<UNDEF>").strip()
        return maker, model

    @override
    def __str__(self) -> str:
        stat: dict[str, dict[str, int]] = {}
        for task in self.tasks:
            maker, model = task.result()
            x: dict[str, int] = stat.setdefault(maker, {})
            y = x.setdefault(model, 0)
            x[model] = y + 1
        r = ""
        for maker in sorted(stat.keys()):
            for model in sorted(stat[maker].keys()):
                r += f"{maker: >25} | {model: >40} | {stat[maker][model]:<5}\n"
        return r


class NoCam(BasicProcessor[str]):
    """Finds photos w/o camera maker/model"""

    @override
    @staticmethod
    def process(f: str):
        p = Photo(f)
        return (
            f
            if p.get("Exif.Image.Make") == "" or p.get("Exif.Image.Model") == ""
            else ""
        )

    @override
    def __str__(self) -> str:
        lst: list[str] = []
        for task in self.tasks:
            f = task.result()
            if f:
                lst.append(f)
        return "\n".join(lst)


class Hugin(BasicProcessor[tuple[str, str]]):
    """Finds Hugin-processed photos"""

    @override
    @staticmethod
    def process(f: str):
        p = Photo(f)
        software = p.get("Exif.Image.Software")
        return (f, software) if "Hugin" in software else ("", "")

    @override
    def __str__(self) -> str:
        res: dict[str, str] = {}
        for task in self.tasks:
            f, s = task.result()
            if f:
                res[f] = s
        return "\n".join(f"{upto60(k): >60} | {v: <30}" for k, v in res.items())


class NoGPS(BasicProcessor[str]):
    """Find photos without GPS tag"""

    @override
    @staticmethod
    def process(f: str):
        p = Photo(f)
        return (
            f
            if (
                p.get("Exif.GPSInfo.GPSLatitude") == ""
                or p.get("Exif.GPSInfo.GPSLongitude") == ""
            )
            else ""
        )

    @override
    def __str__(self) -> str:
        lst: list[str] = []
        for task in self.tasks:
            s = task.result()
            if s:
                lst.append(s)
        return "\n".join(lst)


class NoGPSDir(BasicProcessor[tuple[str, bool]]):
    @override
    @staticmethod
    def process(f: str):
        p = Photo(f)
        nogps = (
            p.get("Exif.GPSInfo.GPSLatitude") == ""
            or p.get("Exif.GPSInfo.GPSLongitude") == ""
        )
        return os.path.dirname(f), nogps

    @override
    def __str__(self) -> str:
        res: dict[str, dict[bool, int]] = {}
        for task in self.tasks:
            dirname, nogps = task.result()
            d2 = dirname.removeprefix(self.root)
            x = res.setdefault(d2, {True: 0, False: 0})
            x[nogps] += 1
        return "\n".join(
            f"{v[True]:3} / {v[False]:<3} {k}"
            for k, v in sorted(res.items(), key=lambda x: x[1][True])
            if v[True] > 0
        )


class SameTag(BasicProcessor[list[tuple[str, str]]]):
    @override
    @staticmethod
    def process(f: str):
        p = Photo(f)
        return [(k, str(p.get(k, "FAIL")).encode().decode("unicode-escape")) for k in p.exif_keys]

    @override
    def __str__(self) -> str:
        @dataclasses.dataclass
        class Cnt:
            val: str
            cnt: int

        tags: dict[str, Cnt] = {}
        for task in self.tasks:
            for k, v in task.result():
                if k not in tags:
                    tags[k] = Cnt(v, 1)
                else:
                    if tags[k].val == v:
                        tags[k].cnt += 1
                    else:
                        tags[k] = Cnt("<DIFFERENT>", -1)

        return "\n".join(
            f"{y.cnt:5} | {x:50} | {y.val}"
            for x, y in sorted(tags.items(), key=lambda x: x[1].cnt)
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
    with concurrent.futures.ProcessPoolExecutor() as executor:
        print(modes[args.mode](root=args.root, exclude=args.exclude, executor=executor))
