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
config = {
    'listeners': {
        'default': {
            'type': 'tcp',
            'bind': '0.0.0.0:1883',
        },
        'ws-mqtt': {
            'bind': '127.0.0.1:8080',
            'type': 'ws',
            'max_connections': 10,
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
broker = Broker(config=config)
                        #"auth": {"plugins": ['auth.anonymous'], "allow-anonymous": True}})
app = web.Application()
aiohttp_jinja2.setup(app, loader=jinja2.FileSystemLoader('./www/tmpl'))


async def game_handler(request):
    context = {'foo': 'bar'}
    response = aiohttp_jinja2.render_template('game.html', request, context)
    return response


async def host_handler(request):
    context = {"clues": []}
    for file in os.listdir("www/static/clues"):
        context["clues"].append(clue(".".join(file.split(".")[:-1]), file, "img"))
    response = aiohttp_jinja2.render_template('host.html',
                                              request,
                                              context)
    return response


async def config_handler(request):
    context = {}
    response = aiohttp_jinja2.render_template('config.html',
                                              request,
                                              context)
    return response

app.router.add_get('/game', game_handler)
app.router.add_get('/', game_handler)
app.router.add_get('/host', host_handler)
app.router.add_get('/config', config_handler)
app.add_routes([web.static('/static', './www/static', show_index=True)])

timergoing = False
timer = datetime.timedelta(hours=1)


async def timerfunc():
    print("hi")
    await asyncio.sleep(1)
    C = MQTTClient()
    await C.connect('mqtt://localhost')
    print("timer connected")
    global timer
    while 1:
        timer -= datetime.timedelta(seconds=1)
        minutes, seconds = divmod(timer.total_seconds(), 60)
        await C.publish('timer', "{:02d}:{:02d}".format(int(minutes), int(seconds)).encode(), qos=QOS_2)
        await asyncio.sleep(1)


async def print_timer():
    await asyncio.sleep(1)
    C = MQTTClient()
    await C.connect('mqtt://localhost')
    await C.subscribe([
            ('timer', QOS_2),
         ])
    while 1:
        message = await C.deliver_message()
        packet = message.publish_packet
        print("%s => %s" % (packet.variable_header.topic_name, str(packet.payload.data)))

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    formatter = "[%(asctime)s] :: %(levelname)s :: %(name)s :: %(message)s"
    logging.basicConfig(level=logging.INFO, format=formatter)
    try:
        tasks = [asyncio.ensure_future(web._run_app(app, port=80)),
                 asyncio.ensure_future(broker.start()),
                 asyncio.ensure_future(timerfunc()),
                 asyncio.ensure_future(print_timer()),
                 ]
        loop.run_until_complete(asyncio.wait(tasks))
    except KeyboardInterrupt:  # pragma: no cover
        pass
    finally:
        web._cancel_all_tasks(loop)
        loop.run_until_complete(loop.shutdown_asyncgens())
        loop.close()