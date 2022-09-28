import json
import logging
import uuid

from flask import Flask, render_template, request, abort, make_response

from const import EXPRESSION_LENGTH
from expressions import is_valid_expression, evalute_expression
from sql import sql_context, init_db
from utils import get_random_expression, get_game_id, set_finished_in_db, get_game_answer

# from flask_cors import CORS
# from werkzeug.middleware.proxy_fix import ProxyFix

log = logging.getLogger('werkzeug')
log.setLevel(logging.WARN)

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)

init_db()

app = Flask(__name__)
# app.wsgi_app = ProxyFix(app.wsgi_app, x_for=1)
# CORS(app)


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
    result = evalute_expression(expression)
    key = str(uuid.uuid4())
    with sql_context() as cur:
        cur.execute("""INSERT INTO game (expression, key) VALUES (?, ?)""", (expression, key))
        last_row_id = cur.lastrowid

    resp = {"id": last_row_id, "key": key, "wordID": game_id, "result": result}
    logger.debug(f"route/start_game: {resp}")
    return api_response(resp)


@app.route("/api/v1/guess/", methods=["POST"])
def guess_word():
    json_resp = request.get_json(force=True)
    logger.debug(json_resp)
    guess = json_resp["guess"]
    game_id = json_resp["id"]

    if not (len(guess) == EXPRESSION_LENGTH and is_valid_expression(guess)):
        logger.info(f"Invalid expression with guess: {guess}")
        return abort(400, "Invalid expression!")

    with sql_context() as cur:
        cur.execute("""SELECT expression, guesses, finished FROM game WHERE id = (?)""", (game_id,))
        try:
            answer, guesses, finished = cur.fetchone()
        except TypeError:
            logger.info(f"Invalid expression with game id: {game_id}")
            return abort(500)
    logger.info(f"got {(answer, guesses, finished)}")

    guesses = guesses.split(",")

    if len(guesses) > 6 or finished:
        return abort(404, "Game is already finished!")

    guesses.append(guess)
    guesses = ",".join(guesses)

    if guesses[0] == ",":
        guesses = guesses[1:]

    with sql_context() as cur:
        cur.execute("""UPDATE game SET guesses = (?) WHERE id = (?)""", (guesses, game_id))
    logger.info("executed update")

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

    logger.debug(f"route/guess_word: {guess_status}")
    return api_response(guess_status)


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
