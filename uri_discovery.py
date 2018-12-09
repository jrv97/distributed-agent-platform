""" Esto es lo que se ejecuta en cada nodo de Chord """
import socket
import time
from random import choice
import Pyro4
from zeroconf import ServiceBrowser, ServiceInfo, Zeroconf

from settings import REFRESH_RATE_CONTACT_NETWORK, TIMEOUT_CONTACT_NETWORK


def register_uri_as_service(uri, ip, port):
    """
     Used to register an entrypoint to Chord
     network.
    """
    zero = Zeroconf()
    service = ServiceInfo(
        "c._http._tcp.local.",
        "%sc._http._tcp.local." % str(uri)[9:],
        socket.inet_aton(ip), port, 0, 0,
        {'path': None},
    )
    print("Uri %s registrada" % uri)
    zero.register_service(service)


class ServiceListener(object):
    """
    Custom zeroconf listener that is trying to find
    the chord_entrypoint service.
    """
    available_uris = []

    def remove_service(self, zeroconf, type, name):
        uri = "PYRO:obj_" + name[0:-19]
        self.available_uris.remove(uri)
        print(uri, "is now not available")

    def add_service(self, zero, type, name):
        uri = "PYRO:obj_" + name[0:-19]
        self.available_uris.append(uri)
        print(uri, "is now available")

    def find_zombie_uris(self):
        for uri in self.available_uris:
            try:
                with Pyro4.Proxy(uri) as n:
                    if not n.ping():
                        self.available_uris.remove(uri)
                        print("Uri %s was zombie, now deleting" % uri)
            except:
                self.available_uris.remove(uri)
                print("Uri %s was zombie, now deleting" % uri)



def get_entrypoint_service():
    """
    Tries to find an available uri until timeout
    Returns chord node uri
    """
    zero = Zeroconf()
    listener = ServiceListener()
    ServiceBrowser(zero, "c._http._tcp.local.", listener)
    listener.find_zombie_uris()
    start_time = time.time()
    while len(listener.available_uris) == 0:
        if (time.time() - start_time > TIMEOUT_CONTACT_NETWORK):
            zero.close()
            raise TimeoutException(
                "Timeout on trying to contact chord network")
        time.sleep(REFRESH_RATE_CONTACT_NETWORK)
    zero.close()
    print(listener.available_uris)
    return choice(listener.available_uris)


class TimeoutException(Exception):
    """
    Exception raised when a timeout was hit.
    """

    def __init__(self, msg=("Timeout.")):
        super(TimeoutException, self).__init__(msg)
