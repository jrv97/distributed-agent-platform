import Pyro4
from termcolor import colored
from threading import Thread
from time import sleep

from chord_node import Chord_Node
from misc import log, open_closed, sets_diff, at_least_one_func_in_common
from settings import (HASH_SPACE_BITS, TIMEOUT_CHECK_KEYS, TIMEOUT_DELETE_KEYS,
                      TIMEOUT_PRINT_DATA_NODE_INFO, TIMEOUT_REPLICATE)


@Pyro4.expose
class Data_Node(Chord_Node):

    # region Class Properties

    @property
    def data(self):
        return self.__data

    @data.setter
    def data(self, x):
        self.__data = x

    @property
    def hoster(self):
        return self.__hoster

    @hoster.setter
    def hoster(self, x):
        self.__hoster = x

    # endregion

    def __init__(self, id, hoster, name=None):
        """
        ID es el identificador que tendra este nodo en la red, similar a un nodo Chord.
        """
        Chord_Node.__init__(self, id)
        self.__data = {}
        self.__hoster = hoster

        # threads
        self.replication_thread = Thread(
            name='replication-thread' + str(self.id),
            target=self.replicate_background,
            args=(TIMEOUT_REPLICATE,))
        self.replication_thread.start()
        self.keys_checking_thread = Thread(
            name='keys-checking-thread' + str(self.id),
            target=self.check_keys_background,
            args=(TIMEOUT_CHECK_KEYS,))
        self.keys_checking_thread.start()
        self.deleting_thread = Thread(
            name='deleting-thread' + str(self.id),
            target=self.delete_background,
            args=(TIMEOUT_DELETE_KEYS,))
        self.deleting_thread.start()
        self.print_info_thread = Thread(
            name='print-info-thread' + str(self.id),
            target=self.print_data_background,
            args=(TIMEOUT_PRINT_DATA_NODE_INFO,))
        self.print_info_thread.start()

    def insert(self, key, value):
        if self.is_responsible_for(key):
            if self.data.__contains__(key):
                msg = colored('Node %d already contained key "%d", previous value was "%s", now changing to "%s".' % (
                    self.id, key, self.data[key].value, value), 'red')
                log(msg)
            self.data[key] = Data(value, state='primary')
        else:
            self.find_successor(key).insert(key, value)

    def delete(self, key):
        if self.is_responsible_for(key):
            if self.data.__contains__(key):
                # self.data[key].state == 'deleted'
                self.data.__delitem__(key)
                return True
            return False
        else:
            return self.find_successor(key).delete(key)

    def lookup(self, key):
        if self.is_responsible_for(key):
            return self.data.get(key)
        else:
            return self.find_successor(key).lookup(key)

    def get_keys_to_replicate(self):
        """
        Devuelve el conjunto de datos que pertenecen al rango de llaves
        del nodo
        """
        return {x: self.data[x] for x in self.data.keys() if self.is_responsible_for(x)}

    def get_data_of_sort(self, state):
        """
        Devuelve los key-value pairs de los datos que se encuentran en
        el estado state, que puede ser '?', 'primary', 'secondary' o 'deleted'
        """
        return [x for x in self.data.items() if x[1].state == state]

    def replicate(self, ctrl_c):
        """
        Recibe un diccionario ctrl_c que son los datos que se quieren
        replicar (o copiar, o hacerles ctrl_v... duh!). Se encarga de
        actualizar la replica que ya tiene a partir de ctrl_c, y si algun
        dato secundario ya no se tiene que replicar lo marca como deleted.
        """
        # primero hay que ver de las que me mandan a replicar cuales aun
        # no tengo e insertar esas en mis datos como secundarias
        my_sec_keys = [x[0] for x in self.get_data_of_sort('secondary')]
        ctrl_c_keys = [x[0] for x in ctrl_c]
        missing = sets_diff(ctrl_c_keys, my_sec_keys)
        for x in missing:
            v = self.find_value_from_key_in_ctrl_c(x, ctrl_c)
            self.data[x] = Data(v, 'secondary')
        # luego hay que ver si de las que tengo marcadas como secundarias
        # hay alguna que ya no la deba tener, y si es asi la borro
        for x in my_sec_keys:
            if x not in ctrl_c_keys:
                self.data[x] = Data(self.data[x].value, 'deleted')
        # outdated = sets_diff(my_sec_keys, ctrl_c)
        # for x in outdated:
        #     self.data[x] = Data(self.data[x], 'deleted')

    def find_value_from_key_in_ctrl_c(self, key, ctrl_c):
        for i in range(len(ctrl_c)):
            if ctrl_c[i][0] == key:
                return ctrl_c[i][1].value

    def replicate_background(self, timeout):
        """
        Se encaga de ir replicando los datos en el sucesor del nodo.
        Siempre se esta ejecutando en background cada timeout tiempo.
        """
        while True:
            if self.connected and not self.locked:
                # primary key value pairs
                pkv = [x for x in self.data.items() if x[1].state == 'primary']
                if len(pkv) > 0:
                    ########################## PACOTILLA PARA IMPRIMIR ##########################
                    msg = 'Key(s):\n'
                    for x in pkv:
                        k = ' - (%s : %s)\n' % (x[0], x[1].value)
                        msg = msg + k
                        msg = msg + \
                            'found to be primary of node %d. Replicating on successor...' % (
                                self.id)
                        msg = colored(msg, 'blue')
                        log(msg)
                    #############################################################################
                    try:
                        self.successor.replicate(pkv)
                    except Exception as e:
                        msg = colored('Exception "%s" raised in "replicate_background" at node %d' % (
                            e, self.id), 'red')
                        log(msg)
                        self.handle_successor_fail()
            sleep(timeout)

    def check_keys_background(self, timeout):
        """
        Revisa que los datos del nodo se encuentren en el estado correcto,
        y si no, los arregla. Siempre se esta ejecutando en background cada
        timeout tiempo.
        """
        while True:
            if self.connected and not self.locked:
                # primero hay que ir por cada dato de los que tiene guardados
                # el nodo y marcar como primarios los que pertenezcan a su rango
                # de llaves
                for k in self.data.keys():
                    if self.is_responsible_for(k):
                        # if self.data[k].state != 'primary' and self.data[k].state != 'deleted':
                        self.data[k].state = 'primary'
                        msg = colored('%d is now a primary key of node %d.', 'blue') % (
                            k, self.id)
                        log(msg)
                    # si hay algun dato que no pertenezca al rango de llaves del nodo pero este
                    # marcado como primario, significa que otro nodo ya se encarga de este, entonces
                    # lo marcamos como secundario aunque luego se elimine
                    elif self.data[k].state == 'primary':
                        self.data[k].state = 'secondary'
                        msg = colored('%d is now a secondary key of node %d.', 'red') % (
                            k, self.id)
                        log(msg)
            sleep(timeout)

    def is_responsible_for(self, key):
        """
        Devuelve True ssi. key pertenece al rango de llaves del nodo
        """
        try:
            return open_closed(key, self.predecessor.id, self.id)
        except Exception as e:
            msg = colored('Exception "%s" raised in is_responsible_for at node %d' %
                          (e, self.id), 'red')
            log(msg)
            self.handle_predecessor_fail()

    def delete_background(self, timeout):
        """
        Cada timeout tiempo elimina todos los datos del nodo que esten marcados como 'deleted'
        """
        while True:
            if self.connected and not self.locked:
                byebye = self.get_data_of_sort('deleted')
                for x in byebye:
                    if not self.is_responsible_for(x[0]):
                        msg = colored(
                            'Node %d found storing key %s unnecessary and will delete it.', 'blue') % (self.id, x[0])
                        log(msg)
                        self.data.__delitem__(x[0])
            sleep(timeout)

    def get_valid_fingers(self):
        ans = []
        for i in range(HASH_SPACE_BITS):
            f = self.fingers[i]
            try:
                ans.append(self.fingers[i].node.hoster)
            except Exception as e:
                msg = colored(
                    'Exception "%s" raised in get_valid_fingers at node %d' % (e, self.id), 'red')
                log(msg)
                self.handle_finger_fail(i)
        return ans

    def get_keys_in_range(self, start, end):
        ret = [(key, self.data[key].value)
               for key in self.data.keys() if open_closed(key, start, end)]
        return ret

    def save_keys_in_notify(self):
        """
        Cuando el notify de Chord detecta que es necesario replicar llaves pq el predecesor fallo o pq la
        estructura del anillo esta incorrecta, de forma que el predecesor del nodo cambia, entonces se
        ejecuta este metodo. Se llama desde notify, que esta definido como "abstracto" en Chord y aqui lo
        redefino pq no es tarea de Chord replicar.
        """
        try:
            predecesor_id = self.predecessor.id
            try:
                info = self.successor.get_keys_in_range(
                    predecesor_id, self.id)
                for key, value in info:
                    if key in self.data.keys():
                        self.data[key].state = 'primary'
                    else:
                        self.data[key] = Data(value, 'primary')
            except Exception as e:
                msg = colored('Exception "%s" raised in "save_keys_in_notify" (1) at node %d.' % (
                    e, self.id), 'red')
                log(msg)
                self.handle_successor_fail()
        except Exception as e:
            msg = colored('Exception "%s" raised in "save_keys_in_notify" (2) at node %d.' % (
                e, self.id), 'red')
            log(msg)
            self.handle_predecessor_fail()

    def print_data_background(self, timeout):
        while True:
            sleep(timeout)
            self.print_data()

    def print_data(self):
        if len(self.data) > 0:
            data = self.data
            msg = '------------------------------------------\n'
            msg += colored("Node %d's stored data:\n" % self.id, 'blue')
            for k, v in data.items():
                msg += '------------------------------------------\n'
                item = 'Agent ID: %s\n%s\n' % (v.value.aid, self.data_to_row(
                    k, v.value.name, v.value.ip, v.value.port, v.state))
                msg += item
                msg += '------------------------------------------\n'
                log(msg)

    def data_to_row(self, k, vname, vip, vport, vstate):
        row = '|_ Key: %s\n|_ Value:\n|  |_ Name: %s\n|  |_ IP: %s\n|  |_ Port: %s\n|_ State: "%s"' % (
            k, vname, vip, vport, vstate)
        return row

    def get_agents_by_funcs(self, funcs):
        me = self.id
        ags = []
        # caso base
        current = self.successor

        # iterar por el anillo
        try:
            # print(
            #     "Va a iterar por el anillo!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
            current_id = current.id
            while me != current_id:
                # print(
                #     "Entro al while con su siguiente !!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                for _, v in current.data.items():
                    # print(
                    #     "Entro al for de los data items!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                    ag = v.value
                    state = v.state
                    # print(
                    #     "Viendo agente!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", ag.aid)
                    ag_funcs = ag.functionalities
                    # print("Funcs ->", ag_funcs)
                    if state != 'deleted' and at_least_one_func_in_common(funcs, ag_funcs):
                        ags.append(ag)
                        # print(
                        #     "Le hizo append a algo!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
                current = current.successor
                current_id = current.id
        except Exception as e:
            msg = colored(
                'Exception "%s" raised in "get_agents_by_func" at node %d.' % (e, current.id))
            log(msg)
            current.handle_successor_fail()
            return False, ags
        return True, ags

    def get_agents_by_id(self, aid):
        me = self.id
        # caso base
        print("Los items!!!!!!!!!!!!!!!!!!!!!!!", self.data.items())
        for _, v in self.data.items():
            if v.value.aid == aid:
                print("El valiu!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!", v.value)
                return v.value
        # iterar por el anillo
        current = self.successor
        try:
            current_id = current.id
            while me != current_id:
                for _, v in current.data.items():
                    state = v.state
                    if state != 'deleted' and v.value.aid == aid:
                        return v.value
                current = current.successor
                current_id = current.id
        except Exception as e:
            msg = colored(
                'Exception "%s" raised in "get_agents_by_id" at node %d.' % (e, current.id))
            log(msg)
            current.handle_successor_fail()
            return None
        return None


class Data:
    def __init__(self, value, state='?'):
        """
        Representa el value de un key-value pair de un dato del nodo.
        value es el valor que tomara esa llave en el diccionario de datos
        y state puede ser '?', 'primary', 'secondary' o 'deleted'.
        (defaults to '?')
        """
        self.value = value
        self.state = state

    def __str__(self):
        return 'Data = (%s, %s)' % (self.value, self.state)
