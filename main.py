from aiohttp import web
import asyncio
import jinja2
import aiohttp_jinja2
from hbmqtt.broker import Broker
import logging
import random
import datetime
import os
from collections import namedtuple
from hbmqtt.client import MQTTClient, ClientException
from hbmqtt.mqtt.constants import QOS_1, QOS_2
import crontab
import inspect
import importlib
from collections import ChainMap
import os
import itertools

Plugin = namedtuple('plugin', ['instance', 'crons', 'mqtts', 'services'])

async def foo():
    print("hi")

class ERM:
    broker_config = {
        'listeners': {
            'default': {
                'type': 'tcp',
                'bind': '127.0.0.1:1883',
            },
            'ws-mqtt': {
                'bind': '127.0.0.1:8080',
                'type': 'ws',
            },
        },
        'sys_interval': 10,
        'auth': {
            'allow-anonymous': True,
            'password-file': os.path.join(os.path.dirname(os.path.realpath(__file__)), "passwd"),
            'plugins': [
                'auth_file', 'auth_anonymous'
            ]

        },
        'topic-check': {
            'enabled': True,
            'plugins': [
                'topic_taboo'
            ]
        }
    }

    def __init__(self, loop=None):
        self.loop = loop
        if self.loop == None:
            self.loop = asyncio.get_event_loop()
        self.broker = Broker(config=self.broker_config)
        self.app = web.Application()
        aiohttp_jinja2.setup(self.app, loader=jinja2.FileSystemLoader('./www/tmpl'))
        self.app.add_routes([web.static('/static', './www/static', show_index=True)])

        self.timergoing = False
        self.timer = datetime.timedelta(hours=1)

        self.MQTT = MQTTClient()

        # self.crons = {"foo": (crontab.CronTab("*/1 * * * * * *"), [foo])}
        self.tosub = []
        self.plugins = {}

    @property
    def crons(self):
        return ChainMap(*[p.crons for p in self.plugins.values()])

    @property
    def mqtts(self):
        return ChainMap(*[p.mqtts for p in self.plugins.values()])

    @property
    def services(self):
        return [print(x) or x[1] for p in self.plugins.values() for k in p.services.values() for x in k]

    def load_plugin_file(self, plugin):
        handlers = []
        temp = importlib.machinery.SourceFileLoader(plugin, os.path.dirname(
            os.path.abspath(__file__)) + "/plugins/" + plugin).load_module()
        for name, Class in inspect.getmembers(temp, lambda x: inspect.isclass(x) and hasattr(x, "_plugin")):
            print("found class: " + name)
            handlers.append(Class)
            self.load_plugin(plugin, Class)
        return handlers

    def load_plugin(self, name, plugin, config=None):
        if config is None:
            config = {}
        print("loading plugin: " + plugin.__name__ + " / " + name)
        crons = {}
        mqtts = {}
        services = {}
        www = {}
        instance = plugin(self)
        for _, func in inspect.getmembers(instance):
            if hasattr(func, "_crons"):
                for cr in func._crons:
                    if cr not in crons:
                        c = crontab.CronTab(cr)
                        now = datetime.datetime.utcnow()
                        crons[cr] = \
                            [c, now + datetime.timedelta(seconds=c.next(now=datetime.datetime.utcnow(), default_utc=True)), []]
                    crons[cr][-1].append(func)
            if hasattr(func, "_topics"):
                for t, qos in func._topics:
                    if t not in mqtts:
                        mqtts[t] = []
                    mqtts[t].append((qos, func))
            if hasattr(func, '_services'):
                for s in func._services:
                    if s not in services:
                        services[s] = []
                    services[s].append((func, asyncio.ensure_future(func())))
            if hasattr(func, '_www'):
                for route in func._www:
                    if route not in www:
                        www[route] = func
                        self.app.router.add_get(route, func)

        self.plugins[name] = Plugin(instance=instance, crons=crons, mqtts=mqtts, services=services)

    async def connectMQTT(self):
        while not self.broker.transitions.is_state("started", self.broker.transitions.model):
            await asyncio.sleep(1)
        await self.MQTT.connect('mqtt://localhost')

    async def mqtt_in(self):
        try:
            while not self.broker.transitions.is_state("started", self.broker.transitions.model):
                await asyncio.sleep(1)

            print("starting mqtt in")
            await self.MQTT.subscribe([('game/#', QOS_2)]) # this needs to be here or it doesnt work?
            while 1:
                message = await self.MQTT.deliver_message()
                packet = message.publish_packet
                _, _, topic = packet.variable_header.topic_name.partition("/")
                logging.debug("%s %s => %s" % (packet.variable_header.topic_name, topic, str(packet.payload.data)))
                if topic in self.mqtts:
                    for _, f in self.mqtts[topic]:
                        self.loop.create_task(f(message))
        except Exception as e:
            print("error")
            print(e)
            #if self.mqtts


    async def cronshim(self):
        funcs = []
        while 1:
            now = datetime.datetime.utcnow()
            if funcs:
                for pc in funcs:
                    c, nextrun, funcs = self.crons[pc]
                    if (nextrun - now).total_seconds() < 0.01:
                        self.crons[pc][1] = \
                            nextrun + datetime.timedelta(seconds=c.next(now=datetime.datetime.utcnow(), default_utc=True))
                        for func in funcs:
                            self.loop.create_task(func())
                funcs = []
            nxt, fnc = None, []
            for cp, (crn, nextrun, [*fnk]) in self.crons.items():
                if nxt is None or nextrun < nxt:
                    nxt, fnc = nextrun, [cp]
                elif nextrun == nxt:
                    fnc.append(cp)

            if nxt is None:
                delay = 60
            else:
                delay = (nxt - now).total_seconds()
                funcs = fnc
            await asyncio.sleep(delay)

    def run(self):
        for file in os.listdir("plugins"):
            if file.endswith(".py"):
                print("file: " + file)
                self.load_plugin_file(file)
        self.loop.run_until_complete(self.start())

    async def start(self):
        try:
            tasks = [
                     self.loop.create_task(web._run_app(self.app, port=80)),
                     self.loop.create_task(self.broker.start()),
                     self.loop.create_task(self.mqtt_in()),
                     self.loop.create_task(self.connectMQTT()),
                     self.loop.create_task(self.cronshim()),
                     ] + self.services
            print("tasks ", tasks)
            await asyncio.wait(tasks, loop=self.loop)
        except KeyboardInterrupt:
            raise
        finally:
            web._cancel_all_tasks(self.loop)
            await self.loop.shutdown_asyncgens()
            self.loop.close()









if __name__ == '__main__':
    print("starting")
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    e = ERM()
    e.run()