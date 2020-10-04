import datetime
import threading
from emcee_server import Server


def execute(server: Server, username: str, mode: str = None, value: int = None):
    if 'death_punishment' not in server.player_data[username] \
            or 'end_time' not in server.player_data[username]['death_punishment'] \
            or server.player_data[username]['death_punishment']['end_time'] is None:
        server.tell_player('You are not imprisoned')
        return False
    end_time = server.player_data[username]['death_punishment']['end_time']
    now = datetime.datetime.now()
    delta0 = end_time - now
    delta1 = delta0 - datetime.timedelta(seconds=1)
    delta2 = delta1 - datetime.timedelta(seconds=1)
    server.send_command(f'title {username} times 0 20 0')
    server.send_command(f'title {username} subtitle {{"text":"remaining in sentence","color":"#FF0000"}}')
    server.send_command(f'title {username} title {{"text":"{str(delta0).split(".", 2)[0]}","color":"#FF0000"}}')
    if delta1 > datetime.timedelta(seconds=0):
        threading.Timer(1, server.send_command, (f'title {username} title {{"text":"{str(delta1).split(".", 2)[0]}",'
                                                 f'"color":"#FF0000"}}',)).start()
    if delta2 > datetime.timedelta(seconds=0):
        threading.Timer(2, server.send_command, (f'title {username} title {{"text":"{str(delta2).split(".", 2)[0]}",'
                                                 f'"color":"#FF0000"}}',)).start()
    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Freedom] can\'t be purchased with emeralds')
    return 0


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, '[Freedom] is ready to use')
    return True
