import asyncio
import importlib
import pkgutil
from typing import Any, Literal

import terminaltexteffects.effects
from rich.text import Text
from terminaltexteffects.engine.base_effect import BaseEffect
from textual.reactive import reactive, var
from textual.widgets import Static

EffectType = Literal[
    "Beams",
    "BinaryPath",
    "Blackhole",
    "BouncyBalls",
    "Bubbles",
    "Burn",
    "ColorShift",
    "Crumble",
    "Decrypt",
    "ErrorCorrect",
    "Expand",
    "Fireworks",
    "Matrix",
    "MiddleOut",
    "OrbittingVolley",
    "Overflow",
    "Pour",
    "Print",
    "Rain",
    "RandomSequence",
    "Rings",
    "Scattered",
    "Slice",
    "Slide",
    "Spotlights",
    "Spray",
    "Swarm",
    "SynthGrid",
    "Unstable",
    "VHSTape",
    "Waves",
    "Wipe",
]

effects = {}
effect_args = {}
for module_info in pkgutil.iter_modules(
    terminaltexteffects.effects.__path__, terminaltexteffects.effects.__name__ + "."
):
    module = importlib.import_module(module_info.name)
    if hasattr(module, "get_effect_and_args"):
        effect_class, arg_class = module.get_effect_and_args()
        effects[effect_class.__name__] = effect_class
        effect_args[effect_class.__name__] = arg_class


class EffectLabel(Static):

    text: reactive[str] = reactive("")
    height: var[int] = var(0)
    width: var[int] = var(0)
    effect: var[str] = var("beams")
    config: var[dict[str, Any]] = var({})

    def __init__(
        self,
        text: str,
        effect: EffectType = "Beams",
        config: dict[str, Any] = {},
        **kwargs,
    ) -> None:
        super().__init__(text, **kwargs)

        self.text = text
        self.effect = effect
        self.config = config
        self.width = max(len(line) for line in text.split("\n"))
        self.height = text.count("\n")
        self.styles.width = self.width + 2
        self.styles.height = self.height + 2

    async def on_mount(self) -> None:
        pass
        # self.run_worker(self.run_effect())

    async def run_effect(self):
        effect: BaseEffect = effects[self.effect](self.text)
        for key in self.config:
            if hasattr(effect.effect_config, key):
                setattr(effect.effect_config, key, self.config[key])
        print(self.width, self.height)
        effect.terminal_config.canvas_width = self.width
        effect.terminal_config.canvas_height = self.height
        frames = []
        for frame in effect:
            frames.append(frame)
        for frame in frames:
            print("step")
            self.text = frame
            self.update(Text.from_ansi(self.text))
            await asyncio.sleep(0)
