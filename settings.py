# Network specific parameters/settings

import pickle
import Pyro4

# cantidad de bits en las llaves de los nodos chord
HASH_SPACE_BITS = 16
# size de las llaves de los nodos chord
HASH_SPACE_SIZE = 2**HASH_SPACE_BITS

# timeouts
TIMEOUT_CHECK_SUCCESSOR = .5
TIMEOUT_STABILIZE = .5
TIMEOUT_FIX_FINGERS = .5
TIMEOUT_CHECK_KEYS = 1
TIMEOUT_REPLICATE = 3
TIMEOUT_DELETE_KEYS = 5
TIMEOUT_WAIT_FOR_CONNECTION = 2
TIMEOUT_CONTACT_NETWORK = 0.5
TIMEOUT_PRINT_NODE_INFO = 90
TIMEOUT_PRINT_DATA_NODE_INFO = 60
# para esperar un tiempo limitado antes de asumir que hubo un fallo en la red
Pyro4.config.COMMTIMEOUT = 15

# otros parametros
TRIES_KILL_WAIT_FOR_CONNECTION = 5
TRIES_CONTACT_NETWORK = 3
REFRESH_RATE_CONTACT_NETWORK = 0.3

# para serializar en la red usando pickle
Pyro4.config.SERIALIZERS_ACCEPTED.add('pickle')
Pyro4.config.SERIALIZER = 'pickle'
Pyro4.config.THREADPOOL_SIZE = 300

# para hacer broadcast en toda la red
Pyro4.config.NS_BCHOST = '255.255.255.255'
