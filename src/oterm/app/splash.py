import random
from typing import Any

from textualeffects.effects import EffectType
from textualeffects.widgets import SplashScreen

logo = """
         @@@@@@.                      :@@@@@@
        @@@@@@@@@                    @@@@@@@@@
       @@@@= @@@@@                  @@@@@ =@@@@
      %@@@%   @@@@.                .@@@@   %@@@%
      @@@@    .@@@@                @@@@.    @@@@
      @@@@     @@@@  @@@@@@@@@@@@  @@@@     @@@@
      @@@@     @@@@@@@@@@@@@@@@@@@@@@@@     @@@@
      @@@@     @@@@@@@@        @@@@@@@@     @@@@
      @@@@    .@@@@@              @@@@@.    @@@@
      @@@@@@@@@@@@.                .@@@@@@@@@@@@
     @@@@@@@@@@@@                    @@@@@@@@@@@@
   #@@@@@*                                  *@@@@@#
  @@@@@                                        @@@@@
 @@@@@                                          @@@@@
=@@@@                                            @@@@=
@@@@                                              @@@@
@@@@         -         +@@@@@@+         -         @@@@
@@@@      .@@@@@   :@@@@@@@@@@@@@@:   @@@@@.      @@@@
@@@@      %@@@@@  @@@@          @@@@  @@@@@%      @@@@
=@@@@       @@  .@@@              @@@.  @@       @@@@=
 @@@@@          @@@     *@@@@:     @@@          @@@@@
  %@@@@         @@@       @@       @@@         @@@@%
  @@@@:         @@@       @@       @@@         :@@@@
 @@@@.           @@@@            @@@@           .@@@@
:@@@@              @@@@@@@@@@@@@@@@              @@@@.
@@@@-                 =@@@@@@@@=                 -@@@@
@@@@                                              @@@@
@@@@:                                            :@@@@
*@@@                                              @@@*
 @@@@                                            @@@@
 #@@@@                                          @@@@#
  %@@@@                                        @@@@@
  #@@@@                                        @@@@#
  @@@@                                          @@@@
 @@@@=                                          =@@@@
 @@@@                                            @@@@
 @@@@                                            @@@@
 @@@@                                            @@@@
    @.                                          .@
"""

effects: list[tuple[EffectType, dict[str, Any]]] = [
    (
        "Beams",
        {
            "beam_delay": 3,
            "beam_gradient_steps": 2,
            "beam_gradient_frames": 2,
            "final_gradient_steps": 2,
            "final_gradient_frames": 2,
            "final_wipe_speed": 5,
        },
    ),
    (
        "BouncyBalls",
        {
            "ball_delay": 1,
        },
    ),
    (
        "Expand",
        {
            "movement_speed": 0.1,
        },
    ),
    (
        "Pour",
        {
            "pour_speed": 3,
        },
    ),
    (
        "Rain",
        {},
    ),
    (
        "RandomSequence",
        {},
    ),
    (
        "Scattered",
        {},
    ),
    (
        "Slide",
        {},
    ),
]

effect, config = random.choice(effects)
splash = SplashScreen(text=logo, effect=effect, config=config)
