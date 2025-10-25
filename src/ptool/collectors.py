import asyncio
from collections.abc import Awaitable, Sequence


def right(n: int, x: str) -> str:
    return x if len(x) < n else f"…{x[-(n - 1) :]}"


def left(n: int, x: str) -> str:
    return x if len(x) < n else f"{x[: (n - 1)]}…"


async def two_level(tasks: Sequence[Awaitable[tuple[str, str]]]) -> str:
    stat: dict[str, dict[str, int]] = {}
    async for task in asyncio.as_completed(tasks):
        maker, model = await task
        x: dict[str, int] = stat.setdefault(maker, {})
        y = x.setdefault(model, 0)
        x[model] = y + 1
    r = ""
    for maker in sorted(stat.keys()):
        for model in sorted(stat[maker].keys()):
            r += f"{maker: >25} | {model: >40} | {stat[maker][model]:<5}\n"
    return r


async def simple_list(tasks: Sequence[Awaitable[str]]) -> str:
    lst: list[str] = []
    async for task in asyncio.as_completed(tasks):
        f = await task
        if f != "":
            lst.append(f)
    return "\n".join(lst)


async def key_value(tasks: Sequence[Awaitable[tuple[str, str]]]) -> str:
    res: dict[str, str] = {}
    async for task in asyncio.as_completed(tasks):
        f, s = await task
        if f:
            res[f] = s
    return "\n".join(
        f"{right(60, k): >60} | {left(30, ' '.join(v.split())): <30}" for k, v in res.items()
    )


async def nogpsdir(tasks: Sequence[Awaitable[tuple[str, bool]]]) -> str:
    res: dict[str, dict[bool, int]] = {}
    async for task in asyncio.as_completed(tasks):
        dirname, nogps = task.result()
        # d2 = dirname.removeprefix(self.root)
        x = res.setdefault(dirname, {True: 0, False: 0})
        x[nogps] += 1
    return "\n".join(
        f"{v[True]:3} | {v[False]:3} | {k}"
        for k, v in sorted(res.items(), key=lambda x: x[1][True])
        if v[True] > 0
    )


async def stats(tasks: Sequence[Awaitable[str]]) -> str:
    res: dict[str, int] = {}
    async for task in asyncio.as_completed(tasks):
        val = await task
        if val in res:
            res[val] += 1
        else:
            res[val] = 1
    return "\n".join(f"{v:6} | {k}" for k, v in sorted(res.items(), key=lambda x: x[1]))
