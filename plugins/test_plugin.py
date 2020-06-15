from wrappers import plugin, cron, service, onMqtt, www
import asyncio
import logging
from main import ERM


#@plugin
class myPlugin:
    def __init__(self, e: ERM):
        self.e = e

    #@cron("*/1 * * * * * *")
    def foo(self):
        logging.info("hello every second")

    @cron("*/3 * * * * * *", runlevel=1)
    def foo1(self):
        logging.info("hello every three seconds")

    @cron("*/2 * * * * * *")
    def foo3(self):
        logging.info("hello every two second")

    @service(runlevel=1)
    async def bar(self):
        x = 20
        while x > 1:
            await asyncio.sleep(1)
            print("hello from a service")
            x -= 1




    #@onMqtt("timer")
    #def x(self, message):
    #    hbmqtt.
