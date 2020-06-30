from props.prop import prop, Button
from collections import namedtuple

Relay = namedtuple('Relay', ['name', 'pin', 'description'])


class relayboard(prop):
    def __init__(self, name="relayboard", topic="relay", relays=16, names_descriptions=None, **kwargs):
        super().__init__(name=name, template_file="relayboard.html", **kwargs)
        self.relays = []
        self.topic = topic
        for i in range(relays):
            found = False
            if names_descriptions is not None:
                if i < len(names_descriptions):
                    found = True
                    name = names_descriptions[i][0]
                    description = names_descriptions[i][1]
            if not found:
                name = str(i)
                description = "relay {}".format(i)

            self.relays.append(Relay(name, i, description))