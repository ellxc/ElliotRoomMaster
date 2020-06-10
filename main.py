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

clue = namedtuple("clue", ['id', 'src', 'type'])
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

        self.app.router.add_get('/game', self.game_handler)
        self.app.router.add_get('/', self.game_handler)
        self.app.router.add_get('/host', self.host_handler)
        self.app.router.add_get('/config', self.config_handler)
        self.app.add_routes([web.static('/static', './www/static', show_index=True)])

        self.timergoing = False
        self.timer = datetime.timedelta(hours=1)

        self.MQTT = MQTTClient()

        # self.crons = {"foo": (crontab.CronTab("*/1 * * * * * *"), [foo])}

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
        found = False
        for name, Class in inspect.getmembers(temp, lambda x: inspect.isclass(x) and hasattr(x, "_plugin")):
            print("found class: " + name)
            handlers.append(Class)
            self.load_plugin(plugin, Class)
            found = True
        if not found:
            raise Exception("no such plugin to load or file did not contain a plugin")
        return handlers

    def load_plugin(self, name, plugin, config=None):
        if config is None:
            config = {}
        print("loading plugin: " + plugin.__name__ + " / " + name)
        crons = {}
        mqtts = {}
        services = {}
        instance = plugin()
        for _, func in inspect.getmembers(instance):
            if hasattr(func, "_crons"):
                for cr in func._crons:
                    if cr not in crons:
                        crons[cr] = (crontab.CronTab(cr), [])
                    crons[cr][1].append(func)
            if hasattr(func, "_topics"):
                for t in func._topics:
                    if t not in mqtts:
                        mqtts[t] = []
                    mqtts[t].append(func)
            if hasattr(func, '_services'):
                for s in func._services:
                    if s not in services:
                        services[s] = []
                    services[s].append((func, asyncio.ensure_future(func())))

        self.plugins[name] = Plugin(instance=instance, crons=crons, mqtts=mqtts, services=services)


    async def game_handler(self, request):
        context = {'foo': 'bar'}
        response = aiohttp_jinja2.render_template('game.html', request, context)
        return response

    async def host_handler(self, request):
        context = {"clues": []}
        for file in os.listdir("www/static/clues"):
            context["clues"].append(clue(".".join(file.split(".")[:-1]), file, "img"))
        response = aiohttp_jinja2.render_template('host.html', request, context)
        return response

    async def config_handler(self, request):
        context = {}
        response = aiohttp_jinja2.render_template('config.html', request, context)
        return response

    async def connectMQTT(self):
        while not self.broker.transitions.is_state("started", self.broker.transitions.model):
            await asyncio.sleep(1)
        await self.MQTT.connect('mqtt://localhost')

    async def print_timer(self):
        await self.MQTT.subscribe([
            ('timer', QOS_2),
        ])
        while 1:
            message = await self.MQTT.deliver_message()
            packet = message.publish_packet
            print("%s => %s" % (packet.variable_header.topic_name, str(packet.payload.data)))

    async def timertick(self):
        while 1:
            self.timer -= datetime.timedelta(seconds=1)
            minutes, seconds = divmod(self.timer.total_seconds(), 60)
            await self.MQTT.publish('timer', "{:02d}:{:02d}".format(int(minutes), int(seconds)).encode(), qos=QOS_2)
            await asyncio.sleep(1)

    async def cronshim(self):
        funcs = []
        while 1:
            if funcs:
                for func in funcs:
                    await func()
                funcs = []
            now = datetime.datetime.utcnow()
            nxt, fnc = None, []
            for crn, [*fnk] in self.crons.values():
                if nxt is None or crn.next(now=now, default_utc=True) < nxt.next(now=now, default_utc=True):
                    nxt, funcs = crn, [*fnk]
                elif crn.next(now=now, default_utc=True) == nxt.next(now=now, default_utc=True):
                    for fnkk in fnk:
                        funcs.append(fnkk)

            if nxt is None:
                delay = 60
            else:
                delay = nxt.next(now=now, default_utc=True)
            await asyncio.sleep(delay)

        self.loop.call_later(delay, lambda: self.cronshim(*fnc))

    def run(self):
        for file in os.listdir("plugins"):
            if file.endswith(".py"):
                print("file: " + file)
                self.load_plugin_file(file)
        self.loop.run_until_complete(self.start())

    async def start(self):
        try:
            tasks = [
                    #asyncio.ensure_future(web._run_app(self.app, port=80)),
                     #asyncio.ensure_future(self.broker.start()),
                     #asyncio.ensure_future(self.timertick()),
                     #asyncio.ensure_future(self.connectMQTT()),
                     #asyncio.ensure_future(self.print_timer()),
                     asyncio.ensure_future(self.cronshim()),
                     ] + self.services
            print(tasks)
            await asyncio.wait(tasks)
        except KeyboardInterrupt:
            raise
        finally:
            web._cancel_all_tasks(self.loop)
            #self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()









if __name__ == '__main__':
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    e = ERM()
    e.run()