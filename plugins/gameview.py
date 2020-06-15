from wrappers import plugin,  www
from main import ERM
import aiohttp_jinja2

@plugin
class gameviewer:

    def __init__(self, e: ERM):
        self.e = e

    @www("/")
    @www("/game")
    async def game_handler(self, request):
        context = {'foo': 'bar'}
        response = aiohttp_jinja2.render_template('game.html', request, context)
        return response