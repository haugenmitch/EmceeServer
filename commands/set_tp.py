import datetime
from emcee_server import Server

SET_TP_COST = 10
SET_TP_DELAY_S = SET_TP_COST * 3600


def execute(server: Server, username: str, mode: str = None, value: int = None):
    if __cooldown_helper__(server, username) is not None:
        server.warn_player(username, '[Set Teleport] is still in cooldown')
        return False
    location = server.get_player_location(username)
    if location is None:
        server.warn_player(username, 'Your location could not be found')
        return False
    if server.get_player_item_count(username, 'minecraft:emerald') < SET_TP_COST or not \
            server.remove_player_items(username, 'minecraft:emerald', SET_TP_COST):
        server.warn_player(username, 'You do not have enough emeralds')
        return False
    server.player_data[username]['tp']['destination'] = {'x': location['x'], 'y': location['y'], 'z': location['z'],
                                                         'realm': location['realm']}
    server.laud_player(username, 'Teleport location set')
    server.player_data[username]['set_tp']['cooldown'] = datetime.datetime.now() \
                                                         + datetime.timedelta(seconds=SET_TP_DELAY_S)

    return True


def cost(server: Server, username: str, mode: str = None, value: int = None):
    server.tell_player(username, f'[Set Teleport] costs {SET_TP_COST} emerald{"" if SET_TP_COST == 1 else "s"}')
    return SET_TP_COST


def cooldown(server: Server, username: str, mode: str = None, value: int = None):
    cd = __cooldown_helper__(server, username)
    if cooldown is None:
        server.tell_player(username, '[Set Teleport] is ready to use')
        return True
    else:
        server.tell_player(username, f'[Set Teleport] cooldown time remaining: {str(cd).split(".", 2)[0]}')
        return False


def __cooldown_helper__(server: Server, username: str):
    now = datetime.datetime.now()
    cd = server.player_data[username]['set_tp']['cooldown'] if 'cooldown' in server.player_data[username]['set_tp'] \
        else now
    if cd <= now:
        return None
    else:
        return cd - now
