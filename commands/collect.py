import datetime
import math
from emcee_server import Server

HOURS_PER_EMERALD = 24


def execute(server: Server, username: str, mode: str = None, value: int = None):
    log_ons = server.player_data[username]['log_ons']
    log_offs = server.player_data[username]['log_offs']
    now = datetime.datetime.now()
    last = server.player_data[username]['collect']['last_collect'] \
        if 'last_collect' in server.player_data[username]['collect'] else None
    remainder = server.player_data[username]['collect']['remainder'] \
        if 'remainder' in server.player_data[username]['collect'] else 0
    total_hours = remainder
    for i in range(len(log_offs)):
        if last is not None and log_offs[i] < last:
            continue
        total_hours += (log_ons[i + 1] - log_offs[i]).total_seconds() / 3600.0
    emeralds = int(total_hours // HOURS_PER_EMERALD)
    remainder = math.fmod(total_hours, HOURS_PER_EMERALD)
    server.player_data[username]['collect']['remainder'] = remainder
    server.player_data[username]['collect']['last_collect'] = now
    if emeralds > 0:
        server.tell_player(username, f'You have earned {emeralds} emerald{"" if emeralds == 1 else "s"}')
        server.send_command(f'give {username} minecraft:emerald {emeralds}')
    else:
        server.tell_player(username, 'You have no emeralds to collect')
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Collect] has no cost')
    return 0


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, '[Collect] is ready to use')
    return True
