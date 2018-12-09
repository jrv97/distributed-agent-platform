import Pyro4
from termcolor import colored

from misc import get_ip, hash, log
from settings import TRIES_CONTACT_NETWORK
from uri_discovery import get_entrypoint_service


class Client:
    def __init__(self):
        self.local_agents = {}
        self.chord_uri = ''
        self.registration_state = {}

    def add_local_agent(self, agent):
        self.local_agents[agent.aid] = agent
        self.registration_state[agent.aid] = 'unregistered'

    def get_local_agents(self):
        return self.local_agents.values()

    def get_local_agent_by_name(self, name):
        return self.local_agents[name + '@' + get_ip() + ':' + '8000']

    def get_local_agent_by_id(self, aid):
        try:
            return self.local_agents[aid]
        except:
            raise Exception("Agent not Found")

    def modify_agent(self, aid, registry_settings):
        agent = self.get_local_agent_by_id(aid)
        previous_key = agent.key
        if agent.active:
            raise Exception("Agent is in Use")
        # ? Para anadir elementos de agente hacerlo aquiiiiiiii
        agent.name = registry_settings['name']
        agent.functionalities = registry_settings['functionalities']
        agent.comments = registry_settings['comments']
        # ?
        previous_state = self.registration_state.pop(aid)

        if previous_state == 'registered':
            self.unregister_agent_distributed(aid, previous_key)
            self.local_agents.pop(aid)
            self.add_local_agent(agent)
            self.register_agent_distributed(agent.aid)
        else:
            self.local_agents.pop(aid)
            self.add_local_agent(agent)
            self.registration_state[agent.aid] = 'unregistered'

    def register_agent(self, registry_settings):
        # ? Para anadir elementos de agente hacerlo aquiiiiiiii
        name = registry_settings['name']
        functionalities = registry_settings['functionalities']
        comments = registry_settings['comments']
        # ?
        agent = Agent(name, functionalities, comments)
        self.add_local_agent(agent)

    def unregister_agent(self, aid):
        try:
            if self.registration_state[aid] == 'registered':
                self.unregister_agent_distributed(aid)
            self.registration_state.pop(aid)
            self.local_agents.pop(aid)
        except:
            raise Exception("Agent Not Found")

    def search_by_func(self, funcs):  # TODO Modificar
        server = self.get_chord_server()
        if server is None:
            return False, None
        else:
            result, agents_list = server.get_agents_by_functionalities(funcs)
            return result, agents_list

    def get_agent_by_id(self, aid):
        server = self.get_chord_server()
        if server is None:
            return False, None
        else:
            agent = server.get_agent_by_id(aid)
            print(agent)
        server._pyroRelease()
        return True, [agent]

    # Para interactuar con chord_Node
    def get_registered_local_agents(self):
        registered = {
            agent.aid: agent for agent in self.local_agents if self.registration_state[agent.aid] == 'registered'}
        return registered

    def get_chord_server(self):
        connected = False
        tries = TRIES_CONTACT_NETWORK
        log(colored("Contacting DAP Servers", 'blue'))
        while tries > 0:
            try:
                uri = get_entrypoint_service()
                connected, server = self.connect_to_server(uri)
                if connected:
                    return server
            except Exception as e:
                print(e)  # ! comentar para expo
                log(colored("DAP Servers not Available on try %d" %
                            (TRIES_CONTACT_NETWORK - tries), 'red'))
                tries -= 1
        return None

    def connect_to_server(self, uri):
        server = Pyro4.Proxy(uri)
        if server.ping():
            log(colored("Connection established with %s!" %server.id, 'green'))
            return True, server
        return False, None

    def register_agent_distributed(self, aid):
        server = self.get_chord_server()
        if server is None:
            return False
        else:
            agent = self.get_local_agent_by_id(aid)
            self.registration_state[aid] = 'registered'
            server.insert_agent(agent)
        server._pyroRelease()
        return True

    def unregister_agent_distributed(self, aid, key=None):
        server = self.get_chord_server()
        if server is None:
            return False
        else:
            server.delete_agent(self.get_local_agent_by_id(aid), key)
            self.registration_state[aid] = 'unregistered'
        server._pyroRelease()
        return True


class Agent:
    def __init__(self, name, functionalities, comments, interfaces=[]):
        self.name = name
        self.active = False

        self.functionalities = functionalities
        self.interfaces = interfaces

        self.comments = comments

        self.ip = get_ip()
        self.port = 8000

    def __str__(self):
        return 'Agent = (%s, %s, %s, %s)' % (self.name, self.key, self.ip, self.port)

    @property
    def aid(self):
        return self.name + '@' + str(self.ip) + ':' + str(self.port)

    @property
    def key(self):
        return hash(self.aid)


def get_name(aid_string):
    name = ""
    for c in aid_string:
        if c != '@':
            name += c
        else:
            break
    return name
