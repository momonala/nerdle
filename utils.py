import logging
from typing import Tuple

import flask
from werkzeug.exceptions import abort

from sql import sql_context

logging.basicConfig(format='%(levelname)s:%(message)s', level=logging.INFO)
logger = logging.getLogger(__name__)


def get_random_expression() -> Tuple[str, str]:
    """Retrieves a random expression from the expressionList table."""
    with sql_context() as cur:
        expression_id, expression = cur.execute(
            """SELECT id, expression FROM expressionList ORDER BY RANDOM() LIMIT 1"""
        ).fetchone()
    logger.info(f"Fetched expression_id: {expression_id} expression: {expression}")
    return expression_id, expression


def get_game_id(request: flask.Request) -> str:
    """Returns the game id associated with the request. On failure, forces a 400 error response."""
    try:
        game_id = request.get_json(force=True)["id"]
        key = request.get_json(force=True)["key"]
        logger.debug(f"Got game: {game_id}, {key}")

        with sql_context() as cur:
            cur.execute("""SELECT key FROM game WHERE key = (?)""", (key,))
            if not cur.fetchone()[0] == key:
                abort(400, "Something went wrong!")

        return game_id
    except (KeyError, TypeError):
        abort(400, "Something went wrong!")


def set_finished_in_db(game_id):
    """Changes the status of a game to finished"""
    with sql_context() as cur:
        cur.execute("""UPDATE game SET finished = true WHERE id = (?) """, (game_id,))
    logger.debug(f"Set finished")


def get_game_answer(game_id) -> str:
    """Get the answer associated with a game"""
    with sql_context() as cur:
        cur.execute("""SELECT expression FROM game WHERE id = (?)""", (game_id,))
        answer = cur.fetchone()
    logger.debug(f"Got answer: {answer}")
    return answer[0]


def init_game_sql(expression: str, key: str) -> str:
    """Create a new game in the SQL database, return the index of the new game."""
    with sql_context() as cur:
        cur.execute("""INSERT INTO game (expression, key) VALUES (?, ?)""", (expression, key))
        latest_game_idx = cur.lastrowid
    return latest_game_idx


def update_game_with_guess_sql(game_id: str, guesses: str):
    """Update the game in SQL with the new guesses. `guesses` is comma separated list of guesses."""
    with sql_context() as cur:
        cur.execute("""UPDATE game SET guesses = (?) WHERE id = (?)""", (guesses, game_id))
    logger.info("executed update")


def get_current_game_sql(game_id: str) -> Tuple[str, str, str]:
    """Return the current game's expression, guesses, and status, given a game id."""
    with sql_context() as cur:
        cur.execute("""SELECT expression, guesses, finished FROM game WHERE id = (?)""", (game_id,))
        try:
            answer, guesses, finished = cur.fetchone()
        except TypeError:
            logger.info(f"Invalid expression with game id: {game_id}")
            abort(500)
    logger.info(f"got {(answer, guesses, finished)}")
    return answer, finished, guesses
