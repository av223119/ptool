import contextlib

has_heif: bool = False
with contextlib.suppress(ImportError):
    import pillow_heif

    pillow_heif.register_heif_opener()
    has_heif = True


def img(f: str) -> bool:
    return f.endswith(".jpg") or (f.endswith(".heic") and has_heif)
