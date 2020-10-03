from emcee_server import Server


def execute(server: Server, username: str, mode: str = None, value: int = None):
    return False


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Freedom] can\'t be purchased with emeralds')
    return 0


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, '[Freedom] is ready to use')
    return True
