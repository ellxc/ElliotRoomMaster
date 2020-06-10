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


clue = namedtuple("clue", ['id', 'src', 'type'])


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
            print("foo")
            self.timer -= datetime.timedelta(seconds=1)
            minutes, seconds = divmod(self.timer.total_seconds(), 60)
            await self.MQTT.publish('timer', "{:02d}:{:02d}".format(int(minutes), int(seconds)).encode(), qos=QOS_2)
            await asyncio.sleep(1)

    def run(self):
        self.loop.run_until_complete(self.start())

    async def start(self):
        try:
            tasks = [asyncio.ensure_future(web._run_app(self.app, port=80)),
                     asyncio.ensure_future(self.broker.start()),
                     asyncio.ensure_future(self.timertick()),
                     asyncio.ensure_future(self.connectMQTT()),
                     asyncio.ensure_future(self.print_timer()),
                     ]
            await asyncio.wait(tasks)
        except KeyboardInterrupt:
            raise
        finally:
            web._cancel_all_tasks(self.loop)
            self.loop.run_until_complete(self.loop.shutdown_asyncgens())
            self.loop.close()









if __name__ == '__main__':
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    e = ERM()
    e.run()