import json
import logging
import uuid
from typing import List, Dict

from flask import Flask, render_template, request, abort, make_response
from flask_cors import CORS
from werkzeug.middleware.proxy_fix import ProxyFix

from const import EXPRESSION_LENGTH
from expressions import is_valid_expression, evalute_expression
from sql import init_db
from utils import (
    get_random_expression,
    get_game_id,
    set_finished_in_db,
    get_game_answer,
    init_game_sql,
    update_game_with_guess_sql,
    get_current_game_sql,
)

log = logging.getLogger('werkzeug')
log.setLevel(logging.WARN)

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

app = Flask(__name__)
app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
CORS(app)


def api_response(json_data):
    resp = make_response(json.dumps(json_data))
    resp.content_type = "application/json; charset=utf-8"
    return resp


# Frontend views
@app.route("/")
def index():
    return render_template("index.html")


# API endpoints
@app.route("/api/v1/start_game/", methods=["POST"])
def start_game():
    """Starts a new game"""
    game_id, expression = get_random_expression()
    answer = evalute_expression(expression)
    key = str(uuid.uuid4())
    game_idx = init_game_sql(expression, key)

    resp = {"id": game_idx, "key": key, "wordID": game_id, "result": answer}
    logger.debug(f"route/start_game: {resp}")
    return api_response(resp)


@app.route("/api/v1/guess/", methods=["POST"])
def guess_word():
    json_resp = request.get_json(force=True)
    logger.debug(json_resp)
    guess = json_resp["guess"]
    game_id = json_resp["id"]

    if not (len(guess) == EXPRESSION_LENGTH and is_valid_expression(guess)):
        return abort(400, "Invalid expression!")

    answer, finished, guesses = get_current_game_sql(game_id)

    if len(guesses.split(",")) > 6 or finished:
        return abort(404, "Game is already finished!")
    guesses += f",{guess}"
    if guesses.startswith(","):
        guesses = guesses[1:]

    update_game_with_guess_sql(game_id, guesses)
    guess_status = generate_guess_keyboard_mapping(answer, guess)

    logger.debug(f"route/guess_word: {guess_status}")
    return api_response(guess_status)


def generate_guess_keyboard_mapping(answer: str, guess: str) -> List[Dict]:
    """Creates the mapping used to color the keyboard in the UI. Returns a list
    EXPRESSION_LENGTH length long, of dicts, where each dict contains a letter (what was
    typed for that position) and a state of values [0, 1, 2] representing if the guessed
    letter is not-present, present but misplaced, or correct.

    Ex. If answer is `86-4` guess is `87-6`, then the function returns:
        [
            {'letter': '8', 'state': 2},
            {'letter': '6', 'state': 0},
            {'letter': '-', 'state': 2},
            {'letter': '6', 'state': 1}
       ]

    """
    guess_status = [{"letter": g_char, "state": 0} for g_char in guess]
    guessed_pos = set()

    for a_pos, a_char in enumerate(answer):
        if a_char == guess[a_pos]:
            guessed_pos.add(a_pos)
            guess_status[a_pos] = {
                "letter": guess[a_pos],
                "state": 2,
            }
    for g_pos, g_char in enumerate(guess):
        if g_char not in answer or guess_status[g_pos]["state"] != 0:
            continue

        positions = []
        f_pos = answer.find(g_char)
        while f_pos != -1:
            positions.append(f_pos)
            f_pos = answer.find(g_char, f_pos + 1)

        for pos in positions:
            if pos in guessed_pos:
                continue
            guess_status[g_pos] = {
                "letter": g_char,
                "state": 1,
            }
            guessed_pos.add(pos)
            break
    return guess_status


@app.route("/api/v1/finish_game/", methods=["POST"])
def finish_game():
    game_id = get_game_id(request)
    set_finished_in_db(game_id)
    answer = get_game_answer(game_id)
    resp = {"answer": answer}

    logger.debug(f"route/finish_game: {resp}")
    return api_response(resp)


if __name__ == "__main__":
    app.run(port=8080)
