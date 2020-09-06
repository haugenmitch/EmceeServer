import datetime
from emcee_server import Server

WALL_COST = 1
BLOCKS_PER_CALL = 20
GROWTH_TIME_S = 10
SHRINK_TIME_S = 86400


def execute(server: Server, username: str, mode: str = None, value: int = None):
    if server.get_player_item_count(username, 'minecraft:emerald') < WALL_COST or not \
            server.remove_player_items(username, 'minecraft:emerald', WALL_COST):
        server.warn_player(username, 'You do not have enough emeralds')
        return False
    server.send_command(f'worldborder add {BLOCKS_PER_CALL} {GROWTH_TIME_S}')
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Wall] costs {WALL_COST} emerald{"" if WALL_COST == 1 else "s"} and expands the '
                                 f'world border {BLOCKS_PER_CALL} blocks per call')
    return WALL_COST


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    return None
