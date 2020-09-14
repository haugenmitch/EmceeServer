import datetime
from emcee_server import Server

WHITELIST_COST = 10


def execute(server: Server, username: str, mode: str = None, value: int = None):
    return False


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Set Teleport] costs {WHITELIST_COST} emerald{"" if WHITELIST_COST == 1 else "s"}')
    return WHITELIST_COST


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    cd = __cooldown_helper__(server, username)
    if cooldown is None:
        server.tell_player(username, '[Whitelist] is ready to use')
        return True
    else:
        server.tell_player(username, f'[Whitelist] cooldown time remaining: {str(cd).split(".", 2)[0]}')
        return False


def __cooldown_helper__(server: Server, username: str):
    now = datetime.datetime.now()
    cd = server.player_data[username]['cooldowns']['whitelist'] if 'set_tp' in \
                                                                   server.player_data[username]['cooldowns'] else now
    if cd <= now:
        return None
    else:
        return cd - now
