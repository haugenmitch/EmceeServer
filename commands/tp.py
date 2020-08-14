from emcee_server import Server


def execute(server: Server, username: str, mode: str, value: int):
    location = server.player_data[username]['tp'] if 'tp' in server.player_data[username] else None
    if location is None:
        return
    server.send_command(f'execute in {location["realm"]} run tp {username} {location["x"]} {location["y"]} '
                        f'{location["z"]}')


def cost(server: Server, username: str, mode: str, value: int):
    server.send_command(f'tellraw {username} "tp costs 1 emerald"')


def cooldown(server: Server, username: str, mode: str, value: int):
    server.send_command(f'tellraw {username} "tp has no cooldown"')
