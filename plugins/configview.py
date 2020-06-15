from wrappers import plugin,  www
from main import ERM
import aiohttp_jinja2

@plugin
class configviewer:

    def __init__(self, e: ERM):
        self.e = e

    @www("/config")
    async def config_handler(self, request):
        context = {}
        response = aiohttp_jinja2.render_template('config.html', request, context)
        return response