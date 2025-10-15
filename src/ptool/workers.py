import os

from PIL import ExifTags, Image

# Exif 3.2 spec, §4.6.5, demands UserComment to be a byte array
# First 8 bytes must be code specification:
# A S C I I 0 0 0
# U N I C O D E 0
# J I S 0 0 0 0 0
# 0 0 0 0 0 0 0 0
# The rest should be comment itself. Unicode flavour is not
# specified, i.e. UTF-16 BE, LE, UTF-8 are all valid.
# In reality, 8 bytes are often not present at all.
usercomment_encoding = {
    b"ASCII\x00\x00\x00": "ascii",
    b"UNICODE\x00": "unicode",
    b"JIS\x00\x00\x00\x00\x00": "jis",
    b"\x00\x00\x00\x00\x00\x00\x00\x00": "undefined",
}


def exif(path: str) -> Image.Exif:
    img = Image.open(path)
    return img.getexif()


async def cams(f: str) -> tuple[str, str]:
    e = exif(f)
    maker = e.get(ExifTags.Base.Make, "<UNDEF>").strip().strip("\x00")
    model = e.get(ExifTags.Base.Model, "<UNDEF>").strip().strip("\x00")
    return maker, model


async def nocam(f: str) -> str:
    e = exif(f)
    if not e.get(ExifTags.Base.Make) or not e.get(ExifTags.Base.Model):
        return f
    return ""


async def nogps(f: str) -> str:
    e = exif(f)
    gps = e.get_ifd(ExifTags.IFD.GPSInfo)
    if not gps.get(ExifTags.GPS.GPSLatitude) or not gps.get(ExifTags.GPS.GPSLongitude):
        return f
    return ""


async def hugin(f: str) -> tuple[str, str]:
    e = exif(f)
    software = e.get(ExifTags.Base.Software, "")
    return (f, software) if "Hugin" in software else ("", "")


async def usercomment(f: str) -> tuple[str, str]:
    e = exif(f)
    ifd = e.get_ifd(ExifTags.IFD.Exif)
    comment = ifd.get(ExifTags.Base.UserComment)
    if comment is None:
        return ("", "")
    if isinstance(comment, str):
        return (f, comment)
    assert isinstance(comment, bytes), f"Type is {type(comment)}"
    if comment[:8] in usercomment_encoding:
        return (f, comment[8:].decode())
    return (f, comment.decode())


async def usercomment_std(f: str) -> str:
    e = exif(f)
    ifd = e.get_ifd(ExifTags.IFD.Exif)
    comment = ifd.get(ExifTags.Base.UserComment)
    if comment is None:
        return "no usercomment"
    if isinstance(comment, str):
        return "non-compliant (str)"
    assert isinstance(comment, bytes), f"Type is {type(comment)}"
    return usercomment_encoding.get(comment[:8], "non-compliant (non-std bytes)")


async def nogpsdir(f: str) -> tuple[str, bool]:
    e = exif(f)
    gps = e.get_ifd(ExifTags.IFD.GPSInfo)
    nogps = not gps.get(ExifTags.GPS.GPSLatitude) or not gps.get(ExifTags.GPS.GPSLongitude)
    return os.path.dirname(f), nogps


async def file_ext(f: str) -> str:
    return f.rsplit(".", maxsplit=1)[1]
