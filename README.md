# Distributed Agent Platform

## Team

- Isabella Hernandez Garcia (C-412)
- Jorge Rodriguez de la Vega (C-412)

## Installation

The team strongly recommends using [pip](https://pip.pypa.io/en/stable/) package manager to install requirements and Python3 interpreter to run the program.

```bash
pip3 install Pyro4
pip3 install json
pip3 install termcolor
pip3 install zeroconf
pip3 install flask
pip3 install flask_bootstrap
```

## Usage in client

Run the following command in the root of the project:

```python
python3 start.py
```

**It is important to know that only one instance of** `start.py` **can be running on each computer.**

Then open any browser and navigate to `localhost:5000`. If everything was done correctly, the main page of the _Distributed Agent Platform_ will be shown for you to interact with it.

## Usage in server

Run the following command in the root of the project:

```python
python3 server.py <identifier>
```

Replacing `<identifier>` with whatever name you want to give to the server you just started. This name will later be hashed to obtain an integer that will serve as the server's _ID_. Therefore, `<identifier>` **must be unique per server started in the entire network**. Each server started will become a node in the _Chord_ network, with the first one initializing it (_i.e. joining the network as seed_) and all others discovering the network and dynamically updating it.
