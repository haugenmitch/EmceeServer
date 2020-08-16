from emcee_server import Server


def execute(server: Server, username: str, mode: str = None, value: int = None):
    location = server.get_player_location(username)
    server.player_data[username]['tp'] = {'x': location['x'], 'y': location['y'], 'z': location['z'],
                                          'realm': location['realm']}


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.send_command(f'tellraw {username} "set_tp costs 1 emerald"')


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.send_command(f'tellraw {username} "set_tp has no cooldown"')
