import json

from flask import Flask, render_template, request
from flask_bootstrap import Bootstrap
from client import Client

app = Flask(__name__)
functionalities = ["Funcionalidad 1", "Funcionalidad 2", "Funcionalidad 3"]


@app.route('/')
def index():
    """  """
    return render_template('index.html', functionalities=functionalities)


@app.route('/result', methods=['POST', 'GET'])
def result():
    if request.method == 'POST':
        result = request.form
    registry_settings = get_agent_registry_settings(result)
    app.client.register_agent(registry_settings)
    return render_template("index.html", functionalities=functionalities)


@app.route('/agents/result', methods=['POST', 'GET'])
def agents_result():
    """ Request to Select Agent """
    agent_aid = ""
    if request.method == 'POST':
        result = request.form
        agent_aid = result['modify']
    agent = app.client.get_local_agent_by_id(agent_aid)
    active_func = active_functionalities(agent)
    registration = 'Unregister' if app.client.registration_state[
        agent_aid] == 'registered' else 'Register'
    return render_template('view_agent.html', agent=agent, functionalities=functionalities, active_func=active_func, registration=registration)


@app.route('/agents/modify', methods=['POST', 'GET'])
def modify_agent():
    if request.method == 'POST':
        result = request.form
    registry_settings = get_agent_registry_settings(result)
    aid = result['aid']
    app.client.modify_agent(aid, registry_settings)
    agent_list = app.client.get_local_agents()
    aid_list = [(agent.aid, app.client.registration_state[agent.aid])
                for agent in agent_list]
    return render_template("agents.html", agent_list=aid_list)


@app.route('/agents/register', methods=['POST', 'GET'])
def register_local_agent():  # ! TODO -> Manejar notificaciones de error al contactar servidor
    if request.method == 'POST':
        result = request.form
    if result['register'] == 'unregistered':
        app.client.register_agent_distributed(result['aid'])
    else:
        print("entro a deregister")
        app.client.unregister_agent_distributed(result['aid'])
    agent_list = app.client.get_local_agents()
    aid_list = [(agent.aid, app.client.registration_state[agent.aid])
                for agent in agent_list]
    return render_template("agents.html", agent_list=aid_list)


@app.route('/agents/remove', methods=['POST', 'GET']) #! Todo -> Manejar notificaciones de error al contactar al server
def remove_agent():
    if request.method == 'POST':
        result = request.form
    aid = result['aid']
    app.client.unregister_agent(aid)
    agent_list = app.client.get_local_agents()
    aid_list = [(agent.aid, app.client.registration_state[agent.aid])
                for agent in agent_list]
    return render_template("agents.html", agent_list=aid_list)


@app.route('/agents')
def agents():
    """ Agents on this pc """
    agent_list = app.client.get_local_agents()
    aid_list = [(agent.aid, app.client.registration_state[agent.aid])
                for agent in agent_list]
    return render_template("agents.html", agent_list=aid_list)


def get_registration(state):
    if state:
        return "registered"
    else:
        return "unregistered"


@app.route('/visual')
def network_visual():
    """ Network Visual  """
    return render_template('network_visualization.html')


########################Search#############################
@app.route('/search')
def search():
    return render_template('search.html', functionalities=functionalities, aid_result=[], func_result=[])


@app.route('/search/search_by_aid', methods=["POST", "GET"])
def search_by_aid():
    if request.method == 'POST':
        result = request.form
        print(result)

    aid_to_find = result['aid_search']
    result = app.client.get_agent_by_id(aid_to_find)
    return render_template('search.html', functionalities=functionalities, aid_result=result[1], func_result=[])


@app.route('/search/search_by_func', methods=["POST", "GET"])
def search_by_func():
    if request.method == 'POST':
        result = request.form
        print(result)
    # Hacer un llamado a Client API
    funcs = get_functionalities(result)
    result, func_result = app.client.search_by_func(funcs)
    print(func_result)
    return render_template('search.html', functionalities=functionalities, aid_result=[], func_result=func_result)

############################################################


def get_agent_registry_settings(result):
    agent_name = result['agent_name']
    agent_func = get_functionalities(result)
    agent_notes = result['notes']
    return {'name': agent_name, 'functionalities': agent_func, 'comments': agent_notes}


def get_functionalities(result):
    agent_func = []
    for func in functionalities:
        try:
            result[func]
            agent_func.append(func)
        except:
            pass
    return agent_func


def initialize_client():
    app.client = Client()
    ###############Inicializar cliente############


def active_functionalities(agent):
    active = {}
    for func in functionalities:
        if agent.functionalities.count(func) != 0:
            active[func] = True
        else:
            active[func] = False
    return active


def start_app():
    Bootstrap(app)
    initialize_client()
    app.run(debug=True)


if __name__ == '__main__':
    Bootstrap(app)
    initialize_client()
    app.run(debug=True)
