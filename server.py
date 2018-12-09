import Pyro4
from json import dumps, loads
from termcolor import colored

from client import Agent
from data_node import Data_Node
from misc import get_ip, hash, log
from settings import TIMEOUT_STABILIZE, TRIES_CONTACT_NETWORK
from uri_discovery import get_entrypoint_service, register_uri_as_service


@Pyro4.expose
class Server:

    # region Class Properties

    @property
    def node(self):
        return self._node

    def ping(self):
        return self.node.ping()

    @node.setter
    def node(self, x):
        self._node = x

    @property
    def id(self):
        return self._id

    def get_id(self):
        return self.id

    @id.setter
    def id(self, x):
        self._id = x

    @property
    def uri(self):
        return self._uri

    @uri.setter
    def uri(self, x):
        self._uri = x

    # endregion Class Properties

    def __init__(self, id):
        self.node = Data_Node(id, self)
        self.id = id
        self.uri = ''
        self.chord_uri = ''

    def connect_to_chord_network(self):
        """
        El nodo intenta encontrar una red de chord, si no lo hace
        inicializa la red.
        """
        connected = False
        tries = TRIES_CONTACT_NETWORK
        log(colored("Contacting Chord Network", 'blue'))
        while tries >= 0:
            try:
                uri = get_entrypoint_service()
                connected = self.connect_to_node(uri)
                if connected:
                    return True
            except:
                log(colored("Chord Network not Available on try %d" %
                            (TRIES_CONTACT_NETWORK - tries), 'red'))
                tries -= 1
        return False

    def get_chord_uri(self):
        return self.chord_uri

    def connect_to_node(self, uri):
        with Pyro4.Proxy(uri) as node:
            if node.ping():
                msg = colored('Node %d attempting to join node %d' %
                              (self.id, node.id), 'blue')
                log(msg)
                if self.join(node.get_chord_uri()):
                    self.chord_connection = uri
                    msg = colored('Node %d joined chord network successfully through node %d.' % (
                        self.id, node.id), 'green')
                    log(msg)
                    return True
            msg = colored('Node %d failed joining node %d.' %
                          (self.id, node.id), 'red')
            log(msg)
            return False

    def join(self, chord_uri_to_connect):
        if chord_uri_to_connect is None:
            self.node.join(None)
        else:
            with Pyro4.Proxy(chord_uri_to_connect) as chord_node:
                result, result_message = self.node.join(
                    chord_node if chord_node else None)
                ### pacotilla ###
                color = 'green' if result else 'red'
                msg = colored(result_message, color)
                log(msg)
                #################
                return result

    def get_all_agents(self):
        n = self.node
        ags = self._get_agents_in_dict(n.data)
        n = n.successor
        while n.id != self.id:
            ags += self._get_agents_in_dict(n.data)
        return ags

    def _get_agents_in_dict(self, data):
        ags = []
        for key in data.keys():
            ag = data[key].value
            # TODO: esto no funciona pq aun no hemos hecho el build_agent(json) y hay que arreglar el constructor de Agent para incluir interfaces
            # ags.append(Agent(ag))
        return ags

    def insert_agent(self, ag):
        self.node.insert(ag.key, ag)

    def delete_agent(self, ag, key):
        if key is None:
            key = ag.key
        self.node.delete(key)

    def modify_agent(self, ag):
        self.node.insert(ag.key, ag)

    def get_agent_by_id(self, id):
        """
        Esto es una busqueda de paginas blancas.
        """
        return self.node.get_agents_by_id(id)

    def get_agents_by_functionalities(self, funcs):
        """
        Esto es una busqueda de paginas amarillas.
        """
        return self.node.get_agents_by_funcs(funcs)


if __name__ == '__main__':
    from sys import argv
    # TODO: realmente el id no seria el IP hasheado o algo asi?
    id = str(argv[1])
    id = hash(id)
    node = Server(id)
    with Pyro4.Daemon(get_ip()) as daemon:
        uri = daemon.register(node)
        node.chord_uri = daemon.register(node.node)
        node.uri = uri
        print("Node %d's URI is %s." % (id, uri))
        if not node.connect_to_chord_network():
            msg = colored('Node %d joined chord network as seed' %
                          node.id, 'green')
            log(msg)
            node.join(None)
        register_uri_as_service(node.uri, get_ip(), 8000)
        daemon.requestLoop()
