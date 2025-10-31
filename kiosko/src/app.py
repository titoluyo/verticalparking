from flask import Flask, render_template
app = Flask(__name__)

@app.route('/')
def index():
    return "<h1>Bienvenido al Kiosko</h1><button>Registrar Vehículo</button>"

app.run(host='0.0.0.0', port=80)
