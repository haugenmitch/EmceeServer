from emcee_server import Server


def execute(server: Server, username: str, mode: str, value: int):
    location = server.get_player_location(username)
    server.send_command(f'tellraw {username} "You are at {location["x"]}, {location["y"]}, {location["z"]}, '
                        f'{location["realm"]}"')


def cost(server: Server, username: str, mode: str, value: int):
    server.send_command(f'tellraw {username} "set_tp costs 1 emerald"')


def cooldown(server: Server, username: str, mode: str, value: int):
    server.send_command(f'tellraw {username} "set_tp has no cooldown"')
