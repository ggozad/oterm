import asyncio

from textual.app import ComposeResult
from textual.containers import Container
from textual.screen import ModalScreen
from textual.widgets import Footer, Header, Static

logo = """
        -***-                   :+**=.
        :%@@@@@%:                #@@@@@@-
       .@@@*.*@@@.              %@@%.=@@@-
       *@@%   %@@#             =@@@.  *@@%
       @@@=   -@@@:=*#@@@@@%*=.%@@*   :@@@.
       @@@-   .@@@@@@@%###%@@@@@@@-    @@@-
       @@@-   :@@@@+:       :=%@@@=   .@@@:
       %@@@@@@@@@=             -@@@@@@%@@@.
     .+@@@@%#***-               :***#%@@@@*.
    =@@@#-                             -#@@@*
   *@@@-                                 :%@@%
  =@@@:                                   .@@@=
  %@@*                .:::.                +@@#
  %@@+     +@@%.  :*%@@@%@@@@*-   #@@#     -@@%
  #@@%     @@@@.:%@#=.     .-*@@= %@@@:    *@@*
  .@@@*     :: :@@-   :+=+:   .@@= ::.    =@@@:
   :@@@%       +@#     *@#.    =@%       #@@@-
   -@@@+       :@@-    :+:    .%@=       -@@@+
   @@@*         :%@%+-:::::-=#@@=         -@@@:
  =@@@            :=*%%@@@%%#+:            %@@+
  *@@%                                     +@@*
  +@@@                                     *@@*
  .@@@=                                   :@@@-
   =@@@=                                 :@@@*
    *@@@:                                @@@%
   -@@@=                                 :@@@+
   %@@*                                   =@@@
   @@@-                                   .@@@:
   @@@-                                   .@@@:
"""


class SplashScreen(ModalScreen):
    async def remove_splash(self) -> None:
        await asyncio.sleep(0.5)
        self.app.pop_screen()

    async def on_mount(self) -> None:
        asyncio.create_task(self.remove_splash())

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="splash-container"):
            yield Static(logo, id="splash")
        yield Footer()
