import datetime
from emcee_server import Server


def execute(server: Server, username: str, mode: str = None, value: int = None):
    tithe_cost = __cost_helper__(server, username)
    if server.get_player_item_count(username, 'minecraft:emerald') < tithe_cost or not \
            server.remove_player_items(username, 'minecraft:emerald', tithe_cost):
        server.warn_player(username, 'You do not have enough emeralds')
        return False
    if server.player_data[username]['tithe']['count'] >= server.player_data[username]['death_count']:
        server.warn_player(username, 'You cannot tithe more times than you\'ve died')
        return False
    server.player_data['tithe']['count'] += 1
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    tithe_cost = __cost_helper__(server, username)
    server.tell_player(username, f'[Tithe] costs {tithe_cost} emerald{"" if tithe_cost == 1 else "s"}')
    return tithe_cost


def __cost_helper__(server: Server, username: str):
    tithe_count = server.player_data[username]['tithe']['count'] if 'count' in server.player_data[username]['tithe'] \
        else None
    return 1 if tithe_count is None else tithe_count + 1


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, '[Tithe] is ready to use')
    return True
