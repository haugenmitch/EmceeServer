import math
from emcee_server import Server


def execute(server: Server, username: str, mode: str = None, value: int = None):
    total_cost = __cost_helper__(server, username)
    if total_cost is None:
        return False
    location = server.player_data[username]['tp'] if 'tp' in server.player_data[username] else None
    if location is None:
        return False
    if not server.remove_player_items(username, 'minecraft:emerald', total_cost):
        return False
    server.send_command(f'execute in {location["realm"]} run tp {username} {location["x"]} {location["y"]} '
                        f'{location["z"]}')
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    total = __cost_helper__(server, username)
    if total is None:
        return None
    server.send_command(f'tellraw {username} "tp costs {total} emerald{"" if total == 1 else "s"}"')
    return total


def __cost_helper__(server: Server, username: str):
    current_location = server.get_player_location(username)
    tp_location = server.player_data[username]['tp'] if 'tp' in server.player_data[username] else None
    if current_location is None or tp_location is None:
        return None
    x_diff = abs(current_location['x'] - tp_location['x'])
    y_diff = abs(current_location['y'] - tp_location['y'])
    z_diff = abs(current_location['z'] - tp_location['z'])
    same_realm = current_location['realm'] == tp_location['realm']
    total = math.ceil(math.sqrt(x_diff ** 2 + y_diff ** 2 + z_diff ** 2) / 1000 + (3 if not same_realm else 0))
    return total


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.send_command(f'tellraw {username} "tp has no cooldown"')
