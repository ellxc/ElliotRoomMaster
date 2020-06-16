from props.prop import prop, Button
from collections import namedtuple

Relay = namedtuple('Relay', ['name', 'pin'])


class relayboard(prop):
    def __init__(self, name="relayboard", relays=16):
        super().__init__(name=name, template_file="relayboard.html")
        self.relays = []
        for i in range(relays):
            self.relays.append(Relay(str(i), i))

        self.buttons.append(Button("reset", "relays/on/all", "", "turn on all relays"))
