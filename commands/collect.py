from emcee_server import Server

HOURS_PER_EMERALD = 24


def execute(server: Server, username: str, mode: str = None, value: int = None):
    return False


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Collect] costs {0} emeralds')
    return 0


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, '[Invite] is ready to use')
    return True
