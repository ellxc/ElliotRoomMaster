from abc import ABC, abstractmethod
from collections import namedtuple
from jinja2 import Environment, FileSystemLoader, select_autoescape
from dataclasses import dataclass

#Button = namedtuple('Button', ['name', 'topic', 'data', 'description'])

@dataclass
class Button:
    name: str
    topic: str = ""
    data: str = ""
    description: str = ""
    code: str = ""

    @property
    def onclick(self) -> str:
        if self.code:
            return self.code
        else:
            return "emit('{topic}', '{data}');".format(topic=self.topic, data=self.data)

env = Environment(
    loader=FileSystemLoader('./props/html')
)

class prop():
    def __init__(self, name, template_file=None, buttons=None):
        self.name = name
        if buttons is not None:
            self.buttons = buttons
        else:
            self.buttons = []
        if template_file is not None:
            self.template_file = template_file
        else:
            self.template_file = 'prop-template.html'

    def get_html(self):
        template = env.get_template(self.template_file)
        context = {"prop": self}
        response = template.render(**context)
        return response

