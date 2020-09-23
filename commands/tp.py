import datetime
import math
from emcee_server import Server

TP_RANGE_PER_EMERALD = 1000
TP_COOLDOWN_PER_EMERALD_S = 1000


def execute(server: Server, username: str, mode: str = None, value: int = None):
    total_cost = __cost_helper__(server, username)
    if total_cost is None:
        server.warn_player(username, 'Your teleport destination is not set')
        return False
    destination = server.player_data[username]['tp']['destination'] if 'destination' \
                                                                       in server.player_data[username]['tp'] else None
    if destination is None:
        server.warn_player(username, 'Your teleport destination is not set')
        return False
    if __cooldown_helper__(server, username) is not None:
        server.warn_player(username, '[Teleport] is still in cooldown')
        return False
    if server.get_player_item_count(username, 'minecraft:emerald') < total_cost or not \
            server.remove_player_items(username, 'minecraft:emerald', total_cost):
        server.warn_player(username, 'You do not have enough emeralds')
        return False
    server.send_command(f'execute in {destination["realm"]} run tp {username} {destination["x"]} {destination["y"]} '
                        f'{destination["z"]}')
    server.player_data[username]['tp']['cooldown'] = datetime.datetime.now()\
                                    + datetime.timedelta(seconds=total_cost * TP_COOLDOWN_PER_EMERALD_S)
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    total = __cost_helper__(server, username)
    if total is None:
        server.warn_player(username, 'Your teleport destination is not set')
        return None
    server.tell_player(username, f'[Teleport] costs {total} emerald{"" if total == 1 else "s"}')
    return total


def __cost_helper__(server: Server, username: str):
    current_location = server.get_player_location(username)
    destination = server.player_data[username]['tp']['destination'] if 'destination' in \
                                                                       server.player_data[username]['tp'] else None
    if current_location is None or destination is None:
        return None
    x_diff = abs(current_location['x'] - destination['x'])
    y_diff = abs(current_location['y'] - destination['y'])
    z_diff = abs(current_location['z'] - destination['z'])
    same_realm = current_location['realm'] == destination['realm']
    total = math.ceil(math.sqrt(x_diff ** 2 + y_diff ** 2 + z_diff ** 2) / TP_RANGE_PER_EMERALD +
                      (3 if not same_realm else 0))
    return total


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    cd = __cooldown_helper__(server, username)
    if cooldown is None:
        server.tell_player(username, '[Teleport] is ready to use')
        return True
    else:
        server.tell_player(username, f'[Teleport] cooldown time remaining: {str(cd).split(".", 2)[0]}')
        return False


def __cooldown_helper__(server: Server, username: str):
    now = datetime.datetime.now()
    cd = server.player_data[username]['tp']['cooldown'] if 'cooldown' in server.player_data[username]['tp'] else now
    if cd <= now:
        return None
    else:
        return cd - now
