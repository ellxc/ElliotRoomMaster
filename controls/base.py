from jinja2 import Environment, FileSystemLoader, select_autoescape
from dataclasses import dataclass
from wrappers import controlview

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
    loader=FileSystemLoader('./controls/html/')
)

@controlview
class base():
    def __init__(self, name, *, e, template_file=None, buttons=None, type=None, **kwargs, ):
        self.e = e
        self.name = name
        self.buttons = []
        if buttons is not None:
            b: dict
            for b in buttons:
                but = Button(**b)
                self.buttons.append(but)
        else:
            self.buttons = []
        if template_file is not None:
            self.template_file = template_file
        else:
            self.template_file = 'base.html'
        if kwargs:
            print("warning: unknown arguments ", kwargs)

    def get_html(self):
        template = env.get_template(self.template_file)
        context = {"this": self}
        response = template.render(**context)
        return response


