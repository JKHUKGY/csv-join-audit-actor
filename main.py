"""Apify adapter. Local SDK execution is not a cloud or MCP verification."""
import asyncio

from apify import Actor
from audit import run_report


async def main():
    async with Actor:
        report = run_report(await Actor.get_input())
        await Actor.push_data(report)
        await Actor.set_value('OUTPUT', report)
        Actor.log.info('Join audit finished with verdict: %s', report['verdict'])


if __name__ == '__main__':
    asyncio.run(main())
