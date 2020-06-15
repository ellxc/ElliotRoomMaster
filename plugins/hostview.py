from wrappers import plugin, www
from main import ERM
import aiohttp_jinja2
import os
from collections import namedtuple

clue = namedtuple("clue", ['id', 'src', 'type'])

@plugin
class hostviewer:

    def __init__(self, e: ERM):
        self.e = e

    @www("/host")
    async def host_handler(self, request):
        context = {"clues": []}
        for file in os.listdir("www/static/clues"):
            context["clues"].append(clue(".".join(file.split(".")[:-1]), file, "img"))
        response = aiohttp_jinja2.render_template('host.html', request, context)
        return response