import datetime
from threading import Timer
from emcee_server import Server

WALL_COST = 1
BLOCKS_PER_CALL = 20
GROWTH_TIME_S = 10
SHRINK_TIME_S = 86400
EPSILON = 0.00001


def execute(server: Server, username: str, mode: str = None, value: int = None):
    if 'wall' not in server.server_data:
        server.tell_player(username, 'The world border has not been set yet')
        return False
    if __cooldown_helper__(server) is not None:
        server.warn_player(username, '[Wall] is still in cooldown')
        return False
    if server.get_player_item_count(username, 'minecraft:emerald') < WALL_COST or not \
            server.remove_player_items(username, 'minecraft:emerald', WALL_COST):
        server.warn_player(username, 'You do not have enough emeralds')
        return False

    # The following line handles a Minecraft bug where the growth rate ignores the growth time given.
    # See https://bugs.mojang.com/browse/MC-200233 for more.
    server.send_command(f'worldborder add {EPSILON:.5f}')
    server.send_command(f'worldborder add {BLOCKS_PER_CALL-EPSILON} {GROWTH_TIME_S}')
    server.server_data['wall']['cooldown'] = datetime.datetime.now() + datetime.timedelta(seconds=GROWTH_TIME_S)
    Timer(GROWTH_TIME_S, server.shrink_wall).start()
    server.server_data['wall']['shrinking'] = False
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Wall] costs {WALL_COST} emerald{"" if WALL_COST == 1 else "s"} and expands the '
                                 f'world border {BLOCKS_PER_CALL} blocks per call')
    return WALL_COST


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    cd = __cooldown_helper__(server)
    if cd is None:
        server.tell_player(username, '[Wall] is ready to use')
        return True
    else:
        server.tell_player(username, f'[Wall] cooldown time remaining: {str(cd).split(".", 2)[0]}')
        return False


def __cooldown_helper__(server: Server):
    now = datetime.datetime.now()
    cd = server.server_data['wall']['cooldown'] if 'wall' in server.server_data and 'cooldown' in \
                                                   server.server_data['wall'] else now
    if cd <= now:
        return None
    else:
        return cd - now
