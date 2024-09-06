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

    def compose(self) -> ComposeResult:
        yield Header()
        with Container(id="splash-container"):
            yield Static(logo, id="splash")
        yield Footer()
