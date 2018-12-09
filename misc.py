import Pyro4
import time
from datetime import datetime
from hashlib import pbkdf2_hmac, sha1
from os import urandom
from socket import gethostbyname, gethostname
from termcolor import colored

from settings import *


def open_closed(id, a, b):
    print('%d me llamo con id %d y predecesor %d' %(b, id, a))
    if a < b:
        return id > a and id <= b
    return id > a or id <= b


def open_open(id, a, b):
    if a < b:
        return id > a and id < b
    return id > a or id < b


def closed_open(id, a, b):
    if a == b:
        return False
    if a < b:
        return id >= a and id < b
    return id >= a or id < b


def lock(lock):
    """
    Esto es un decorador. lock es un objeto de tipo threading.Lock
    """
    def wrapper(f):
        """
        f es la funcion a la que se le quiere hacer lock
        """
        def dispatcher(*args, **kwargs):
            """
            dispatcher recibe los argumentos de f.
            Le hace lock() a f, la ejecuta o "dispatchea" con sus argumentos
            y luego le hace release()
            """
            lock.acquire()
            f(*args, **kwargs)
            lock.release()
        return dispatcher
    return wrapper


def gossip(x):
    """
    !!!ESTO ESTA DANDO TREMENDO PALOOOOO!!!
    """
    def wrapper(f):
        def dispatcher(*args, **kwargs):
            id = args[0].__getattribute__(x)
            msg = colored(" -> IN: Node %d attempting to execute %s" %
                          (id, f.__name__), 'blue')
            log(msg)
            f(*args, **kwargs)
            msg = colored(" <- OUT: Node %d executed %s successfully!" %
                          (id, f.__name__), 'green')
            log(msg)
        return dispatcher
    return wrapper


def log(str):
    """
    Metodo para reportar lo que va pasando en la red
    (str es lo que se quiere reportar)
    """
    now = datetime.now()
    ip_addr = get_ip()
    now = "[%d/%d/%d %d:%d:%d %s]" % (now.day,
                                      now.month,
                                      now.year,
                                      now.hour % 12 if now.hour != 12 else 12,
                                      now.minute,
                                      now.second,
                                      'PM' if now.hour >= 12 else 'AM')
    print('%s - - %s \n"%s"\n' % (ip_addr, now, str))


def sets_diff(A, B): return {x for x in A if not B.__contains__(x)}


def at_least_one_func_in_common(funcs, ag_funcs):
    if funcs == []:
        return True
    for x in funcs:
        if ag_funcs.count(x) > 0:
            return True
    return False


def get_nodes_in_network(tag, ns_addr=(None, None)):
    """
    Devuelve todos los nodos que esten conectados a un NS con metadata = tag.
    ns_addr es una tupla (host, port) que se usa para buscar en un NS que este
    corriendo en ese host y por ese puerto en especifico.
    """
    # esto hay que cambiarlo para no usar nameserver
    with Pyro4.locateNS(ns_addr[0], ns_addr[1]) as ns:
        nodes_in_network = map(lambda x: x[1], ns.list(
            metadata_all={tag}).items())
    return nodes_in_network


def get_ip():
    hostname = gethostname()
    ip_addr = gethostbyname(hostname)
    return ip_addr


def hash(x):
    """
    Esta en el libro de Python que tiene un ratoncito que dice Isabella que es una mangosta... (Hitchhicker)
    """
    # V1:
    # salt_len = 16
    # salt = urandom(salt_len)
    # hashed = pbkdf2_hmac(hash_name='sha1', password=bytes(
    #     x, 'utf-8'), salt=salt, iterations=100000)
    # return int.from_bytes(hashed, 'big')
    # V1:
    # hash = hashlib.sha1()
    # hash.update(str(time.time())
    # return hash.hexdigest()[:10]
    # V2: hasheo un string, por ejemplo, el ip
    id = sha1((x).encode('utf-8')).hexdigest()
    # id = int(id, 16) % (10**HASH_SPACE_BITS)
    id = int(id, 16) % HASH_SPACE_SIZE
    return id


# def hash_name_to_get_AID(name):
#     id = sha1((name).encode('utf-8')
#               ).update(str(time.time()).encode('utf-8')).hexdigest()
#     id = int(id, 16) % (10**HASH_SPACE_BITS)
#     return id


class ProxyWrapper(Pyro4.Proxy):
    def __init__(self, proxy):
        uri = proxy._pyroUri
        super(ProxyWrapper, self).__init__(uri)

    def _pyroInvoke(self, methodname, vargs, kwargs, flags=0, objectId=None):
        res = super(ProxyWrapper, self)._pyroInvoke(
            methodname, vargs, kwargs, flags, objectId)
        self._pyroRelease()
        return res
