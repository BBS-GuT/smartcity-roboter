#!/usr/bin/env python3
"""Loopback-only fallback broker for the robot desktop panel."""
import asyncio

from amqtt.broker import Broker


async def main():
    broker = Broker({
        'listeners': {'default': {'type': 'tcp', 'bind': '127.0.0.1:1883'}},
        'plugins': {'amqtt.plugins.authentication.AnonymousAuthPlugin':
                    {'allow_anonymous': True}},
    })
    await broker.start()
    try:
        await asyncio.Event().wait()
    finally:
        await broker.shutdown()


if __name__ == '__main__':
    asyncio.run(main())
