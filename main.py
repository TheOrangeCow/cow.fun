from gevent import monkey
monkey.patch_all()

import os
from flask import Flask, render_template
from jinja2.exceptions import TemplateNotFound
from dotenv import load_dotenv

load_dotenv()

from routes.extensions import socketio
from routes.websitedna import websitedna
from routes.wikiemoji.wikiemoji import wikiemoji
from routes.graveyard.graveyard import graveyard
from routes.wordle import wordle_bp
from routes.pacman.pacman import pacman_bp


app = Flask(__name__)
app.config["SECRET_KEY"] = os.environ.get("SECRET_KEY")

socketio.init_app(app)

# Backends
app.register_blueprint(
    websitedna,
    url_prefix="/websitedna"
)

app.register_blueprint(
    wordle_bp,
    url_prefix="/wordle")

app.register_blueprint(
    wikiemoji,
    url_prefix="/wikiemoji"
)

app.register_blueprint(
    graveyard,
    url_prefix="/graveyard"
)

app.register_blueprint(
    pacman_bp,
    url_prefix="/pacman"
)


# Webpages

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/button")
def button():
    return render_template("button.html")

@app.route("/canvas")
def canvas():
    return render_template("canvas.html")

@app.route("/checkboxs")
def checkboxs():
    return render_template("checkboxs.html")

@app.route("/conquest")
def conquest():
    return render_template("conquest.html")

@app.route("/dontpress")
def dontpress():
    return render_template("dontpress.html")

@app.route("/findbutton")
def findbutton():
    return render_template("findbutton.html")

@app.route("/loading")
def loading():
    return render_template("loading.html")

@app.route("/signup")
def signup():
    return render_template("signup.html")


@app.route("/cowclicker")
def cowclicker():
    return render_template("cowclicker.html")

@app.route("/escape")
def escape():
    return render_template("escape.html")

@app.route("/escapepop")
def escapepop():
    return render_template("escapepop.html")

@app.route("/hackersim")
def hackersim():
    return render_template("hackersim.html")

@app.route("/_paintsim")
def paintsim():
    return render_template("paintsim.html")

@app.route("/stackbuttons")
def stackbuttons():
    return render_template("stackbuttons.html")

@app.route("/websitedna")
def websitedna_page():
    return render_template("websitedna.html")

@app.route("/wikiemoji")
def wikiemoji2():
    return render_template("wikiemoji.html")


@app.route("/graveyard")
def graveyard_page():
    return render_template("graveyard.html")

@app.route("/googlethat")
def googlethat():
    return render_template("googlethat.html")

@app.route("/hacker")
def hacker():
    return render_template("hacker.html")

@app.route("/terra")
def terra_page():
    return render_template("terra.html")

@app.route("/logic")
def logic():
    return render_template("logic.html")

@app.route("/mooer")
def mooer():
    return render_template("mooer.html")

@app.route("/blockparty")
def blockparty():
    return render_template("blockparty.html")

@app.route("/pacman")
def pacman():
    return render_template("pacman.html")

@app.route("/nerd")
def nerd():
    return render_template("nerd.html")

@app.route("/cup")
def cup():
    return render_template("cup.html")

# Home and error pages

@app.route("/index.html")
def indexhtml():
    return render_template("index.html")


@app.route("/<page>")
def pages(page):
    try:
        return render_template(page + ".html")
    except TemplateNotFound:
        return "Page not found", 404


if __name__ == "__main__":

    port = int(os.environ.get("PORT", 5000))

    socketio.run(app, host="0.0.0.0", port=port, debug=True)