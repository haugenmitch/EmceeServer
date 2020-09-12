import datetime
from threading import Timer
from emcee_server import Server

WALL_COST = 1
BLOCKS_PER_CALL = 20
GROWTH_TIME_S = 10
SHRINK_TIME_S = 86400
EPSILON = 0.00001


def execute(server: Server, username: str, mode: str = None, value: int = None):
    if __cooldown_helper__(server) is not None:
        server.warn_player(username, '[Wall] is still in cooldown')
        return False
    if server.get_player_item_count(username, 'minecraft:emerald') < WALL_COST or not \
            server.remove_player_items(username, 'minecraft:emerald', WALL_COST):
        server.warn_player(username, 'You do not have enough emeralds')
        return False
    server.send_command(f'worldborder add {EPSILON:.5f}')  # this line handles a Minecraft bug where the growth rate
    # ignores the growth time given and instead takes on the rate of the worldborder if it is currently
    # growing/shrinking. This line stops the wall movement before setting it again.
    # TODO add this bug to MC bug tracker after testing in 1.16
    server.send_command(f'worldborder add {BLOCKS_PER_CALL-EPSILON} {GROWTH_TIME_S}')
    server.server_data['wall']['cooldown'] = datetime.datetime.now() + datetime.timedelta(seconds=GROWTH_TIME_S)
    server.server_data['wall']['timer'] = Timer(GROWTH_TIME_S, server.shrink_wall)
    server.server_data['wall']['timer'].start()
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
    cd = server.server_data['wall']['cooldown'] if 'cooldown' in server.server_data['wall'] else now
    if cd <= now:
        return None
    else:
        return cd - now
