import abc
import argparse
import concurrent.futures
import contextlib
import dataclasses
import itertools
import os
import typing
from PIL import ExifTags, Image


def upto(n: int, x: str) -> str:
    """shortens string to N characters"""
    return x if len(x) < n else "…%s" % x[-(n - 1) :]


def exif(path: str) -> Image.Exif:
    img = Image.open(path)
    return img.getexif()


class BasicProcessor[T](abc.ABC):
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
        return fn.endswith(".jpg") or (fn.endswith(".heic") and has_heif)

    @typing.override
    def __str__(self) -> str:
        return ""


class Cams(BasicProcessor[tuple[str, str]]):
    """Collects camera maker / model stats"""

    @typing.override
    @staticmethod
    def process(f: str):
        e = exif(f)
        maker = e.get(ExifTags.Base.Make, "<UNDEF>").strip().strip("\x00")
        model = e.get(ExifTags.Base.Model, "<UNDEF>").strip().strip("\x00")
        return maker, model

    @typing.override
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

    @typing.override
    @staticmethod
    def process(f: str):
        e = exif(f)
        return (
            f
            if e.get(ExifTags.Base.Make) == "" or e.get(ExifTags.Base.Model) == ""
            else ""
        )

    @typing.override
    def __str__(self) -> str:
        lst: list[str] = []
        for task in self.tasks:
            f = task.result()
            if f:
                lst.append(f)
        return "\n".join(lst)


class Hugin(BasicProcessor[tuple[str, str]]):
    """Finds Hugin-processed photos"""

    @typing.override
    @staticmethod
    def process(f: str):
        e = exif(f)
        software = e.get(ExifTags.Base.Software, "")
        return (f, software) if "Hugin" in software else ("", "")

    @typing.override
    def __str__(self) -> str:
        res: dict[str, str] = {}
        for task in self.tasks:
            f, s = task.result()
            if f:
                res[f] = s
        return "\n".join(f"{upto(60, k): >60} | {v: <30}" for k, v in res.items())


class UserComment(BasicProcessor[tuple[str, str]]):
    """Finds photos with UserComment"""

    @typing.override
    @staticmethod
    def process(f: str):
        e = exif(f)
        ifd = e.get_ifd(ExifTags.IFD.Exif)
        comment = ifd.get(ExifTags.Base.UserComment)
        if comment is None:
            return ("", "")
        # XXX: Here be dragons!
        # Exif 3.2 spec, §4.6.5, demands UserComment to be a byte array
        # First 8 bytes must be code specification:
        # A S C I I 0 0 0
        # U N I C O D E 0
        # J I S 0 0 0 0 0
        # 0 0 0 0 0 0 0 0
        # The rest should be comment itself. Unicode flavour is not
        # specified, i.e. UTF-16 BE, LE, UTF-8 are all valid.
        # In reality, 8 bytes are often not present at all.
        if isinstance(comment, str):
            return (f, comment)
        assert isinstance(comment, bytes), f"Type is {type(comment)}"
        if comment[:8] in (
            b"ASCII\x00\x00\x00",
            b"UNICODE\x00",
            b"JIS\x00\x00\x00\x00\x00",
            b"\x00\x00\x00\x00\x00\x00\x00\x00",
        ):
            return (f, comment[8:].decode())
        return (f, comment.decode())

    @typing.override
    def __str__(self) -> str:
        res: dict[str, str] = {}
        for task in self.tasks:
            f, s = task.result()
            if f:
                res[f] = s
        return "\n".join(
            f"{upto(60, k): >60} | {' '.join(v[:40].split()): <40}"
            for k, v in res.items()
        )


class NoGPS(BasicProcessor[str]):
    """Find photos without GPS tag"""

    @typing.override
    @staticmethod
    def process(f: str):
        e = exif(f)
        gps = e.get_ifd(ExifTags.IFD.GPSInfo)
        return (
            f
            if (
                not gps.get(ExifTags.GPS.GPSLatitude)
                or not gps.get(ExifTags.GPS.GPSLongitude)
            )
            else ""
        )

    @typing.override
    def __str__(self) -> str:
        lst: list[str] = []
        for task in self.tasks:
            s = task.result()
            if s:
                lst.append(s)
        return "\n".join(lst)


class NoGPSDir(BasicProcessor[tuple[str, bool]]):
    @typing.override
    @staticmethod
    def process(f: str):
        e = exif(f)
        gps = e.get_ifd(ExifTags.IFD.GPSInfo)
        nogps = not gps.get(ExifTags.GPS.GPSLatitude) or not gps.get(
            ExifTags.GPS.GPSLongitude
        )
        return os.path.dirname(f), nogps

    @typing.override
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


class SameTag(BasicProcessor[list[tuple[int, typing.Any]]]):
    @typing.override
    @staticmethod
    def process(f: str):
        e = exif(f)
        return [
            (k, v)
            for k, v in itertools.chain(e.items(), e.get_ifd(ExifTags.IFD.Exif).items())
        ]

    @typing.override
    def __str__(self) -> str:
        @dataclasses.dataclass
        class Cnt:
            val: typing.Any
            cnt: int

        tags: dict[int, Cnt] = {}
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
            f"{y.cnt:5} | {ExifTags.TAGS.get(x, x):50} | {y.val}"
            for x, y in sorted(tags.items(), key=lambda x: x[1].cnt)
        )


has_heif: bool = False
with contextlib.suppress(ImportError):
    import pillow_heif

    pillow_heif.register_heif_opener()
    has_heif = True

modes = {
    "cams": Cams,
    "nocam": NoCam,
    "hugin": Hugin,
    "nogps": NoGPS,
    "nogpsdir": NoGPSDir,
    "sametag": SameTag,
    "comment": UserComment,
}

_parser = argparse.ArgumentParser()
_parser.add_argument(
    "mode",
    action="store",
    type=str,
    choices=list(modes),
)
_parser.add_argument("root", action="store", type=str)
_parser.add_argument("-x", "--exclude", action="append", type=str, default=[])


def main():
    args = _parser.parse_args()
    with concurrent.futures.ProcessPoolExecutor() as executor:
        print(modes[args.mode](root=args.root, exclude=args.exclude, executor=executor))


if __name__ == "__main__":
    main()
