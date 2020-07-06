from controls.base import base
from wrappers import controlview
from collections import namedtuple

Relay = namedtuple('Relay', ['name', 'pin', 'description'])

@controlview
class relayboard(base):
    def __init__(self, name="relayboard", topic="relay", number=16, relays=None, **kwargs):
        super().__init__(name=name, template_file="relayboard.html", **kwargs)
        self.relays = []
        self.topic = topic
        for i in range(number):
            found = False
            if relays is not None:
                if i < len(relays):
                    found = True
                    name = relays[i][0]
                    description = relays[i][1]
            if not found:
                name = str(i)
                description = "relay {}".format(i)

            self.relays.append(Relay(name, i, description))