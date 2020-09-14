import datetime
from emcee_server import Server


def execute(server: Server, username: str, mode: str = None, value: int = None):
    return False


def cost(server: Server, username: str, mode: str = None, value: int = None):
    tithe_cost = __cost_helper__(server, username)
    server.tell_player(username, f'[Tithe] costs {tithe_cost} emerald{"" if tithe_cost == 1 else "s"}')
    return tithe_cost


def __cost_helper__(server: Server, username: str):
    return 1


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    cd = __cooldown_helper__(server, username)
    if cooldown is None:
        server.tell_player(username, '[Tithe] is ready to use')
        return True
    else:
        server.tell_player(username, f'[Tithe] cooldown time remaining: {str(cd).split(".", 2)[0]}')
        return False


def __cooldown_helper__(server: Server, username: str):
    now = datetime.datetime.now()
    cd = server.player_data[username]['cooldowns']['tithe'] if 'tithe' in server.player_data[username]['cooldowns'] \
        else now
    if cd <= now:
        return None
    else:
        return cd - now
