import re
from emcee_server import Server

WHITELIST_COST = 10


def execute(server: Server, username: str, mode: str = None, value: int = None):
    if server.get_player_item_count(username, 'minecraft:emerald') < WHITELIST_COST or not \
            server.remove_player_items(username, 'minecraft:emerald', WHITELIST_COST):
        server.warn_player(username, 'You do not have enough emeralds')
        return False
    server.tell_player(username, 'Enter in chat the name of the player you would like to whitelist')
    output = rf'\<{username}\> (?P<name>\w+)$'
    line, success = server.get_output('', output, timeout=30)
    if not success:
        server.tell_player(username, 'You did not give a username to whitelist')
        server.send_command(f'give {username} minecraft:emerald {WHITELIST_COST}')
        return False
    name = re.search(output, line).group('name')
    line, success = server.get_output(f'whitelist add {name}', rf'Added \w{{{len(name)}}} to the whitelist',
                                      'That player does not exist|Player is already whitelisted')
    if success:
        server.laud_player(username, f'{name} has been invited')
        return True
    else:
        if 'Player is already whitelisted' in line:
            server.tell_player(username, f'{name} has already been invited')
        else:
            server.warn_player(username, f'{name} could not be invited')
        server.send_command(f'give {username} minecraft:emerald {WHITELIST_COST}')
        return False


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Invite] costs {WHITELIST_COST} emeralds')
    return WHITELIST_COST


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, '[Invite] is ready to use')
    return True
