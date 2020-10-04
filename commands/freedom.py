import datetime
import threading
from emcee_server import Server


def execute(server: Server, username: str, mode: str = None, value: int = None):
    end_time = server.player_data[username]['death_punishment']['end_time'] \
        if 'death_punishment' in server.player_data[username] and \
           'end_time' in server.player_data[username]['death_punishment'] else None
    if end_time is None:
        server.tell_player(username, 'You are not imprisoned')
        return False
    now = datetime.datetime.now()
    delta = end_time - now
    server.send_command(f'title {username} times 0 20 0')
    subtitle = f'title {username} subtitle {{"text":"remaining in sentence","color":"#FF0000"}}'
    timeout = datetime.timedelta(seconds=0)
    for i in range(5):
        if delta < timeout:
            break
        msg = f'title {username} title {{"text":"{str(delta).split(".", 2)[0]}","color":"#FF0000"}}'
        threading.Timer(i, server.send_command, (subtitle, )).start()
        threading.Timer(i, server.send_command, (msg, )).start()
        delta -= datetime.timedelta(seconds=1)
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Freedom] can\'t be purchased with emeralds')
    return 0


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, '[Freedom] is ready to use')
    return True
