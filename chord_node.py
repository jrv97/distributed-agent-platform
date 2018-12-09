import Pyro4
import sys
from termcolor import colored
from threading import Lock, Thread
from time import sleep

from misc import ProxyWrapper, closed_open, lock, log, open_closed, open_open
from settings import (HASH_SPACE_BITS, HASH_SPACE_SIZE,
                      TIMEOUT_CHECK_SUCCESSOR, TIMEOUT_FIX_FINGERS,
                      TIMEOUT_PRINT_NODE_INFO, TIMEOUT_STABILIZE)

# remote traceback para ver los errores
sys.excepthook = Pyro4.util.excepthook


@Pyro4.expose
class Chord_Node:
    """
    Representa un nodo de una red tipo Chord (usando Pyro4: una instancia de Pyro4.Proxy)
    """

    # locks para trabajar con el successor y predecessor concurrentemente
    successor_lock = Lock()
    predecessor_lock = Lock()

    # region Class Properties
    @property
    def id(self):
        return self.__id

    @id.setter
    def id(self, x):
        self.__id = x

    @property
    def successor(self):
        return self.fingers[0].node

    @successor.setter
    # @lock(successor_lock)
    def successor(self, x):
        if x.__class__ == Pyro4.Proxy:
            x = ProxyWrapper(x)
        self.fingers[0].node = x

    @property
    def predecessor(self):
        return self.__predecessor

    @predecessor.setter
    # @lock(predecessor_lock)
    def predecessor(self, x):
        if x.__class__ == Pyro4.Proxy:
            x = ProxyWrapper(x)
        self.__predecessor = x

    # endregion

    def __init__(self, id):
        self.id = id
        self.predecessor = None
        self.cache = {}

        # inicializo la finger_table con mi mismo en cada Finger
        self.fingers = [Finger(x, id) for x in range(HASH_SPACE_BITS)]
        self.connected = False
        self.locked = False

        # timeouts de los threads
        stabilize_timeout = TIMEOUT_STABILIZE
        fix_fingers_timeout = TIMEOUT_FIX_FINGERS
        check_successor_timeout = TIMEOUT_CHECK_SUCCESSOR
        print_node_info_timeout = TIMEOUT_PRINT_NODE_INFO
        # threads
        self.stabilize_thread = Thread(
            name='stabilize-thread' + str(self.id),
            target=self.stabilize_background,
            args=(stabilize_timeout,))
        self.fix_fingers_thread = Thread(
            name='fix-fingers-thread' + str(self.id),
            target=self.fix_fingers_background,
            args=(fix_fingers_timeout,))
        # self.check_successor_thread = Thread(
        #     name='check-successor-thread' + str(self.id),
        #     target=self.fix_fingers_background,
        #     args=(check_successor_timeout,))
        self.print_node_info_thread = Thread(
            name='print-node-info-thread' + str(self.id),
            target=self.print_node_info_background,
            args=(print_node_info_timeout,))
        # start threads
        self.stabilize_thread.start()
        self.fix_fingers_thread.start()
        # self.check_successor_thread.start()
        self.print_node_info_thread.start()

    # @gossip('id')
    def join(self, node):
        """
        node es un nodo conocido de la red, se encarga de inicializar
        la finger_table, el sucesor y el predecesor de la instancia y
        de conectarlo "correctamente" a la red.
        """
        # print("ENTRE")
        if node:
            self.predecessor = None
            try:
                # print("Entro a find succesor")
                x = node.find_successor(self.id)
                self.successor = x
                # print("Me uni a: %d" % (self.successor.id))
            except Exception as e:
                msg = colored(
                    'Exception "%s" raised while attempting to join network.' % (e), 'red')
                log(msg)
                return (False, 'Unable to connect to node.')
        else:  # la red estaba vacia
            # print("Aki")
            self.successor = self
            for i in range(HASH_SPACE_BITS):
                # print("It")
                self.fingers[i].node = self
            self.predecessor = self
            # print("Sali")
        self.connected = True
        return (True, 'Connection established successfully!')

    # @gossip('id')
    def find_successor(self, id):
        """
        Encuentra el sucesor inmediato de la llave id en la red.
        """
        try:
            return self.find_predecessor(id).successor
        except Exception as e:
            msg = colored(
                'Exception "%s" raised in "find_successor" at node %d.' % (e, self.id), 'red')
            log(msg)
            return None
        # except Exception as e:
        #     msg = colored('Exception "%s" raised while attempting to find successor for node %d.' % (
        #         e, self.id), 'red')
        #     log(msg)
        #     pass

    # @gossip('id')
    def find_predecessor(self, id):
        """
        Encuentra el predecesor inmediato de la llave id en la red.
        """
        try:
            x = self
            while not open_closed(id, x.id, x.successor.id):
                x = x.closest_preceding_finger(id)
            return x
        except Exception as e:
            msg = colored('Exception "%s" raised in "find_predecessor" at node %d.' % (
                e, self.id), 'red')
            log(msg)
            return None
            # except Exception as e:
            #     msg = colored('Exception "%s" raised while attempting to find predecessor for node %d.' % (
            #         e, self.id), 'red')
            #     log(msg)
            #     pass

    # @gossip('id')
    def closest_preceding_finger(self, id):
        """
        Dado un id, se busca el ultimo nodo de la red con un id
        menor o igual que este.
        """
        for i in range(HASH_SPACE_BITS-1, -1, -1):
            try:
                if self.fingers[i].node and open_open(self.fingers[i].node.id, self.id, id):
                    return self.fingers[i].node
            except Exception as e:
                msg = colored('Exception "%s" raised in "closest_preceding_finger" at node %d.' % (
                    e, self.id), 'red')
                log(msg)
                self.handle_finger_fail(i)
        return self

    # @gossip('id')
    def handle_finger_fail(self, index):
        """
        index es el Finger donde ocurrio un error. Haya lo que haya en esa posicion, si
        no es un nodo de la red, debemos desconectarlo.
        """
        i = index
        if self.fingers[i].node and not isinstance(self.fingers[i].node, Chord_Node):
            self.fingers[i].node._pyroRelease()
        self.fingers[i].node = None
        # id = self.fingers[i].id
        # for i in range(HASH_SPACE_BITS):
        #     if self.fingers[i].id == id:
        #         self.fingers[i].node = None
        msg = colored(
            "Node %d's finger table[%d] failed! Assigned to 'None'" % (self.id, i), 'red')
        log(msg)

    # @gossip('id')
    def stabilize(self):
        try:
            x = self.successor.predecessor
            try:
                pred_id = x.id
                try:
                    if open_open(pred_id, self.id, self.successor.id):
                        self.successor = x
                except Exception as e:
                    msg = colored(
                        'Exception "%s" raised in "stabilize" (1) at node %d.' % (e, self.id), 'red')
                    log(msg)
                    self.handle_successor_fail()
            except Exception as e:
                msg = colored(
                    'Exception "%s" raised in "stabilize" (2) at node %d.' % (e, self.id), 'red')
                log(msg)
            # print("Mi sucesor es: %d" % (self.successor.id))
            self.successor.notify(self)
        except Exception as e:
            msg = colored(
                'Exception "%s" raised in "stabilize" (3) at node %d.' % (e, self.id), 'red')
            log(msg)
            self.handle_successor_fail()

    # @gossip('id')
    def notify(self, node):
        try:
            x = node.id
            try:
                # print("node: %d, pred: %d, id: %d" %
                 #     (node.id, self.predecessor.id, self.id))
                if (not self.predecessor) or open_open(x, self.predecessor.id, self.id):
                 #   print("node.id: %d, x: %d" % (node.id, x))
                    self.predecessor = node
                    msg = colored('Predecessor fixed, value changed to: %d' %
                                  (self.predecessor.id), 'green')
                    log(msg)
                    # ? URGENTE: PREGUNTARLE A ISA
                    ## ESTO ES DE REPLICACION ##
                    self.save_keys_in_notify()
                    ############################
            except Exception as e:
                msg = colored(
                    'Exception "%s" raised in "notify" (1) at node %d.' % (e, self.id), 'red')
                log(msg)
                self.handle_predecessor_fail()
        except Exception as e:
            msg = colored(
                'Exception "%s" raised in "notify" (2) at node %d.' % (e, self.id), 'red')
            log(msg)

    def save_keys_in_notify(self):
        """
        Doest thou mean to thwart our sacred code? If so, alas, thee shall know I, the num-plus-super-ultra-patch,
        the patch to reign above all patches. None shall stop my execution, for it is I, the abstract method! ;)
        -thx, Isy... <3
        """
        pass

    # @gossip('id')
    def handle_successor_fail(self):
        if self.successor and not isinstance(self.successor, Chord_Node):
            self.successor._pyroRelease()
        self.successor = None
        msg = colored("Successor of node %d failed" % self.id, 'red')
        log(msg)
        if not self.assign_new_successor():
            msg = colored("Unable to find find successor to join", 'red')
            log(msg)

    # @gossip('id')
    def handle_predecessor_fail(self):
        if self.predecessor and not isinstance(self.predecessor, Chord_Node):
            self.predecessor._pyroRelease()
        self.predecessor = None
        msg = colored("Predecessor of node %d failed." % self.id, 'red')
        log(msg)

    # @gossip('id')
    def assign_new_successor(self):
        self.locked = True
        for i in range(HASH_SPACE_BITS):
            try:
                if self.fingers[i].node and self.fingers[i].node.ping():
                    self.successor = self.fingers[i].node
                    self.locked = False
                    msg = colored("Successor fixed, value changed to: %d." %
                                  (self.successor.id), 'green')
                    log(msg)
                    return
            except Exception as e:
                msg = colored('Exception "%s" raised in "assign_new_successor" in node %d.' % (
                    e, self.id), 'red')
                log(msg)
                self.handle_finger_fail(i)
        try:
            if self.predecessor and self.predecessor.ping():
                self.successor = self.predecessor
                self.locked = False
                msg = colored("Successor fixed, value changed to: %d" %
                              (self.successor.id), 'green')
                log(msg)
                return
        except Exception as e:
            msg = colored('Exception "%s" raised in assign_new_successor in node %d' % (
                e, self.id), 'red')
            log(msg)
            self.handle_predecessor_fail()
        self.successor = self
        # self.connected = False
        self.locked = False
        msg = colored('Unable to find successor for node %d. Node disconnected.' % (
            self.id), 'red')
        log(msg)

    def ping(self):
        return True

    # @gossip('id')
    def stabilize_background(self, timeout):
        while True:
            if self.connected and not self.locked:
                try:
                    prev_succ_id = self.successor.id
                    self.stabilize()

                    # while unstable
                    while prev_succ_id != self.successor.id:
                        prev_succ_id = self.successor.id
                        self.stabilize()
                except Exception as e:
                    msg = colored("Exception '"+str(e) +
                                  "' raised in: stabilize_background", 'red')
                    log(msg)
                    self.handle_successor_fail()
                sleep(timeout)

    # @gossip('id')
    def fix_fingers_background(self, timeout):
        i = 1
        while True:
            if self.connected and not self.locked:
                # no se updatea el sucesor?
                i = i + 1 if i == 0 else i
                n = self.find_successor(self.fingers[i].start)
                if n.__class__ == Pyro4.Proxy:
                    n = ProxyWrapper(n)
                try:
                    if n:
                        self.fingers[i].node = n
                except Exception as e:
                    msg = colored('Exception "%s" raised in fix_fingers_background (1) at node %d' % (
                        e, self.id), 'red')
                    log(msg)
                try:
                    if n:
                        x = n.id
                        if not self.cache.get(x) and isinstance(n, Pyro4.Proxy):
                            self.cache[x] = Cached_Node(x, n._pyroUri)
                except Exception as e:
                    msg = colored('Exception "%s" raised in fix_fingers_background (2) at node %d' % (
                        e, self.id), 'red')
                    log(msg)
                    # self.handle_finger_fail(i)
                # self.fingers[i].node = self.find_successor(self.fingers[i].start)
                i = (i + 1) % HASH_SPACE_BITS
                sleep(timeout)

    def get_finger(self, i):
        """
        Para pasar la informacion de los fingers por la red y no el Finger.
        La clase Finger da error de serializacion si la uso en otro .py pq
        no la estoy importando en este, sino definiendola, por lo que hace
        "__main__.Finger..." y esto no existe
        """
        return (self.fingers[i].start, self.fingers[i].node)

    def get_nodes_in_finger_table(self):
        ans = []
        for n in self.fingers:
            ans.append(n.node)
        return ans

    def print_node_info(self):
        msg = '------------------------------------------\n'
        msg += colored("Node: %d \n|_ Successor: %s \n|_ Predecessor: %s\n" % (
            self.id, self.successor.id if self.successor else 'None',
            self.predecessor.id if self.predecessor else 'None'),
            'blue')
        msg += colored("|_ Finger table:\n", 'blue')
        for i in range(HASH_SPACE_BITS):
            start, finger = self.fingers[i].start, self.fingers[i]
            msg += "   |_ Finger: %d | Start: %d | Node: %d\n" % (
                i, start, finger.node.id if finger else "-")
        msg += "------------------------------------------\n"
        log(msg)

    def print_node_info_background(self, timeout):
        while True:
            sleep(timeout)
            self.print_node_info()


class Finger:
    """
    Una instancia de Finger es una entrada de la finger table del nodo.
    """

    def __init__(self, i, id):
        self.start = (id + 2 ** i) % HASH_SPACE_SIZE  # !!!
        self.node = None
        self.id = id
        self.index = i
        end = (id + 2 ** (i+1)) % HASH_SPACE_SIZE
        self.interval = (self.start, end)

    def __repr__(self):
        return "Finger %d | Start: %d | Interval: [%d, %d) | Node: %d" % (self.index, self.start, self.interval[0], self.interval[1], self.node)


class Cached_Node:
    def __init__(self, id, uri, missed_pings=0):
        self.id = id
        self.uri = uri
        self.missed_pings = missed_pings

    @property
    def proxy(self):
        return ProxyWrapper(Pyro4.Proxy(self.uri))
