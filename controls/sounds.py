from controls.base import base, env
import os
from dataclasses import dataclass
from wrappers import controlview

@dataclass
class Sound:
    name: str
    src: str


@controlview
class sounds(base):
    def __init__(self, name="sounds", **kwargs):
        super().__init__(name=name, template_file="sounds.html", **kwargs)


    def get_html(self):

        context = {"this": self, "sounds": [], "speakers": self.e.speakers, "speakergroups": self.e.speakergroups}
        for file in os.listdir("www/static/sounds/clues"):
            print(file)
            context["sounds"].append(Sound(".".join(file.split(".")[:-1]), file))

        template = env.get_template(self.template_file)
        response = template.render(**context)
        return response