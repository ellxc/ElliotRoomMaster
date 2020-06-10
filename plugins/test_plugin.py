from wrappers import plugin, cron, service, onMqtt
import asyncio

@plugin
class myPlugin:


    @cron("*/1 * * * * * *")
    def foo(self):
        print ("hello every second")

    @cron("*/3 * * * * * *")
    def foo1(self):
        print("hello every three seconds")

    @service
    async def bar(self):
        x = 20
        while x > 1:
            await asyncio.sleep(1)
            print("hello from a service")
            x -= 1


    #@onMqtt("timer")
    #def x(self, message):
    #    hbmqtt.
