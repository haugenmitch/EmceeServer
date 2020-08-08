from emcee_server import Server


def execute(server: Server = None):
    server.send_command('tp @a ~ ~3 ~')


def cost(server: Server = None):
    return 1
