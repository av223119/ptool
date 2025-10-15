import argparse
import asyncio
import os
from collections.abc import Awaitable, Callable

import ptool.collectors as collector
import ptool.sieves as sieve
import ptool.workers as worker


async def main[T](
    sieve_f: Callable[[str], bool],
    worker_f: Callable[[str], Awaitable[T]],
    collector_f: Callable[[list[Awaitable[T]]], Awaitable[str]],
    root: str,
    exclude: list[str],
):
    tasks: list[Awaitable[T]] = []
    for path, _, files in os.walk(root):
        for f in files:
            ff = os.path.join(path, f)
            if any(x in ff for x in exclude):
                continue
            if sieve_f(ff):
                tasks.append(asyncio.create_task(worker_f(ff), name=ff))
    print(await collector_f(tasks))


modes = {
    "cams": (sieve.img, worker.cams, collector.two_level),
    "nocam": (sieve.img, worker.nocam, collector.simple_list),
    "nogps": (sieve.img, worker.nogps, collector.simple_list),
    "hugin": (sieve.img, worker.hugin, collector.key_value),
    "usercomment": (sieve.img, worker.usercomment, collector.key_value),
    "usercomment-std": (sieve.img, worker.usercomment_std, collector.stats),
    "nogpsdir": (sieve.img, worker.nogpsdir, collector.nogpsdir),
    "ftypes": (lambda _: True, worker.file_ext, collector.stats),
}


def entry():
    _parser = argparse.ArgumentParser()
    _parser.add_argument(
        "mode",
        action="store",
        type=str,
        choices=modes.keys(),
    )
    _parser.add_argument("root", action="store", type=str)
    _parser.add_argument("-x", "--exclude", action="append", type=str, default=[])
    args = _parser.parse_args()
    asyncio.run(
        main(
            sieve_f=modes[args.mode][0],
            worker_f=modes[args.mode][1],
            collector_f=modes[args.mode][2],
            root=args.root,
            exclude=args.exclude,
        )
    )


if __name__ == "__main__":
    entry()
