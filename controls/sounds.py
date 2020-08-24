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
    def __init__(self, name="sounds", soundtrack=None, **kwargs):
        super().__init__(name=name, template_file="sounds.html", **kwargs)
        self.soundtrack = soundtrack if soundtrack is not None else []


    def get_html(self):

        context = {"this": self, "clues": [], "effects":[], "speakers": self.e.speakertags, "speakergroups": self.e.speakergroups}
        for file in os.listdir("www/static/sounds/clues"):
            print(file)
            context["clues"].append(Sound(".".join(file.split(".")[:-1]), "clues/"+file))
        for file in os.listdir("www/static/sounds/effects"):
            print(file)
            context["effects"].append(Sound(".".join(file.split(".")[:-1]), "effects/"+file))

        template = env.get_template(self.template_file)
        response = template.render(**context)
        return response