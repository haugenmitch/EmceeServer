from emcee_server import Server


def execute(server: Server, username: str, mode: str, value: int):
    server.send_command(f'execute at {username} run tp {username} ~ ~{value} ~')


def cost(server: Server, username: str, mode: str, value: int):
    server.send_command(f'tellraw {username} "tp costs 1 emerald"')


def cooldown(server: Server, username: str, mode: str, value: int):
    server.send_command(f'tellraw {username} "tp has no cooldown"')
