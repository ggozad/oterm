from oterm.store.upgrades.v0_1_6 import upgrades as v0_1_6_upgrades
from oterm.store.upgrades.v0_1_11 import upgrades as v_0_1_11_upgrades
from oterm.store.upgrades.v0_2_0 import upgrades as v0_2_0_upgrades
from oterm.store.upgrades.v0_2_4 import upgrades as v0_2_4_upgrades
from oterm.store.upgrades.v0_2_8 import upgrades as v0_2_8_upgrades
from oterm.store.upgrades.v0_3_0 import upgrades as v0_3_0_upgrades
from oterm.store.upgrades.v0_4_0 import upgrades as v0_4_0_upgrades

upgrades = (
    v0_1_6_upgrades
    + v_0_1_11_upgrades
    + v0_2_0_upgrades
    + v0_2_4_upgrades
    + v0_2_8_upgrades
    + v0_3_0_upgrades
    + v0_4_0_upgrades
)
