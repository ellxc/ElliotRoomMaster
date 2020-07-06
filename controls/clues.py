from controls.base import base, env
import os
from dataclasses import dataclass
from wrappers import controlview

@dataclass
class clue:
    id: str
    src: str
    type: str

@controlview
class clues(base):
    def __init__(self, name="clues", **kwargs):
        super().__init__(name=name, template_file="clues.html", **kwargs)


    def get_html(self):

        context = {"this": self, "clues": []}
        for file in os.listdir("www/static/clues"):
            context["clues"].append(clue(".".join(file.split(".")[:-1]), file, "img"))

        template = env.get_template(self.template_file)
        response = template.render(**context)
        return response