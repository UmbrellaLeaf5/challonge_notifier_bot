import io
import signal
import traceback
from datetime import datetime
from threading import Event, Thread

import requests
import resvg_py
import telebot

from config.config import config


# MEANS: экземпляр класса бота
bot = telebot.TeleBot(config["tg_bot_token"])

# MEANS: уже объявленные матчи
notified_matches = set()

# MEANS: предыдущее состояние турнира
tournament_state: list[str | None] = [None]


@bot.message_handler(commands=["start"])
def Start(message):
  """
  Обрабатывает команду /start, отправляя приветственное сообщение.

  Args:
      message: объект сообщения от пользователя.
  """

  bot.reply_to(
    message,
    config["start_message"],
    parse_mode="HTML",
  )


@bot.message_handler(commands=["grid"])
def Grid(message):
  """
  Обрабатывает команду /grid, отправляя в чат изображение турнирной сетки.

  Args:
      message: объект сообщения от пользователя.
  """

  image = FetchTournamentImage()
  bot.send_photo(
    message.chat.id,
    image,
    caption=config["grid_caption"],
    parse_mode="HTML",
  )


def FetchTournamentImage():
  """
  Скачивает SVG турнирной сетки и рендерит в PNG через resvg.

  Returns:
      BytesIO: изображение турнирной сетки в формате PNG.

  Raises:
      HTTPError: если запрос к API завершился ошибкой.
  """

  url = f"https://api.challonge.com/v1/tournaments/{config['tournament_url']}.json"

  response = requests.get(
    url,
    auth=(config["challonge_username"], config["challonge_api_key"]),
    cookies=config["cookies"],
    headers=config["headers"],
  )

  response.raise_for_status()
  tournament = response.json()

  svg_url = tournament["tournament"]["live_image_url"]

  svg_response = requests.get(
    svg_url,
    auth=(config["challonge_username"], config["challonge_api_key"]),
    cookies=config["cookies"],
    headers=config["headers"],
  )

  svg_response.raise_for_status()

  png_bytes = resvg_py.svg_to_bytes(svg_string=svg_response.text)
  return io.BytesIO(png_bytes)


def FetchTournamentInfo():
  """
  Получает информацию о турнире через Challonge API.

  Returns:
      dict: данные турнира.

  Raises:
      HTTPError: если запрос к API завершился ошибкой.
  """

  url = f"https://api.challonge.com/v1/tournaments/{config['tournament_url']}.json"

  response = requests.get(
    url,
    auth=(config["challonge_username"], config["challonge_api_key"]),
    cookies=config["cookies"],
    headers=config["headers"],
  )

  response.raise_for_status()

  return response.json()["tournament"]


def FetchParticipantsByRank(rank: int):
  """
  Находит участников турнира с заданным final_rank.

  Args:
      rank: номер места (1, 2, 3, ...).

  Returns:
      list[str]: список имён участников с данным рангом.
  """

  url = f"https://api.challonge.com/v1/tournaments/{config['tournament_url']}/participants.json"

  response = requests.get(
    url,
    auth=(config["challonge_username"], config["challonge_api_key"]),
    cookies=config["cookies"],
    headers=config["headers"],
  )

  response.raise_for_status()

  names = [
    p["participant"]["name"]
    for p in response.json()
    if p["participant"]["final_rank"] == rank
  ]

  return names


def NotifyTournamentStatus():
  """
  Отслеживает состояние турнира и отправляет уведомления:
  - При старте турнира.
  - При завершении турнира с именем победителя.
  """

  tournament = FetchTournamentInfo()
  state = tournament["state"]

  if tournament_state[0] is None:
    tournament_state[0] = state
    return

  if state == tournament_state[0]:
    return

  if state == "underway" and tournament_state[0] == "pending":
    message = config["tournament_start"].format(
      name=tournament["name"],
      count=tournament["participants_count"],
    )
    bot.send_message(config["tg_chat_id"], message, parse_mode="HTML")

  if state == "complete":
    parts = [config["tournament_complete"].format(name=tournament["name"])]

    rank_keys = {1: "tournament_rank_1", 2: "tournament_rank_2", 3: "tournament_rank_3"}

    for rank, key in rank_keys.items():
      names = FetchParticipantsByRank(rank)

      if names:
        parts.append(config[key].format(names=", ".join(names)))

    bot.send_message(config["tg_chat_id"], "\n".join(parts), parse_mode="HTML")

  tournament_state[0] = state


def FetchMatches():
  """
  Получает все матчи с турнира через Challonge API.

  Returns:
      list: список матчей в формате JSON.

  Raises:
      HTTPError: если запрос к API завершился ошибкой.
  """

  url = (
    f"https://api.challonge.com/v1/tournaments/{config['tournament_url']}/matches.json"
  )

  response = requests.get(
    url,
    auth=(config["challonge_username"], config["challonge_api_key"]),
    cookies=config["cookies"],
    headers=config["headers"],
  )

  response.raise_for_status()

  matches = response.json()

  print(
    f"[{datetime.now().strftime('%H:%M:%S')}]",
    matches,
    "\n\n-----------------------------------\n",
  )

  return matches


def NotifyMatches():
  """
  Проверяет статус матчей и отправляет уведомления в чат:
  - При начале матча.
  - При завершении матча.
  """

  matches = FetchMatches()

  for match in matches:
    match_id = match["match"]["id"]

    player_1_id = match["match"]["player1_id"]
    player_2_id = match["match"]["player2_id"]

    state = match["match"]["state"]
    is_underway = match["match"]["underway_at"]

    if state == "complete" and match_id in notified_matches:
      player_1 = FetchParticipantName(player_1_id)
      player_2 = FetchParticipantName(player_2_id)

      winner = FetchParticipantName(match["match"]["winner_id"])

      message = config["match_winner"].format(
        winner=winner,
        player_1=player_1,
        player_2=player_2,
      )

      bot.send_message(config["tg_chat_id"], message, parse_mode="HTML")
      notified_matches.remove(match_id)

    if state == "open" and is_underway and match_id not in notified_matches:
      player_1 = FetchParticipantName(player_1_id)
      player_2 = FetchParticipantName(player_2_id)

      message = config["match_start"].format(
        player_1=player_1,
        player_2=player_2,
      )

      bot.send_message(config["tg_chat_id"], message, parse_mode="HTML")
      notified_matches.add(match_id)


def FetchParticipantName(participant_id: int):
  """
  Получает название команды/участника по его ID.

  Args:
      participant_id (int): ID участника турнира.

  Returns:
      str: название команды/участника.
  """

  url = f"https://api.challonge.com/v1/tournaments/{config['tournament_url']}/participants/{participant_id}.json"

  response = requests.get(
    url,
    auth=(config["challonge_username"], config["challonge_api_key"]),
    cookies=config["cookies"],
    headers=config["headers"],
  )

  response.raise_for_status()

  participant = response.json()

  return participant["participant"]["name"]


def main():
  """
  Основной цикл программы: проверяет матчи каждые 15 секунд.
  """

  while not stop_event.is_set():
    try:
      NotifyMatches()
      NotifyTournamentStatus()

    except Exception:
      print(
        f"[{datetime.now().strftime('%H:%M:%S')}] Ошибка в цикле опроса:\n"
        f"{traceback.format_exc()}",
      )

    stop_event.wait(15)


if __name__ == "__main__":
  stop_event = Event()

  def _shutdown(signum, frame):
    print(f"[{datetime.now().strftime('%H:%M:%S')}] Завершение работы...")
    stop_event.set()
    bot.stop_polling()

  signal.signal(signal.SIGINT, _shutdown)
  signal.signal(signal.SIGTERM, _shutdown)

  # MEANS: поток для работы бота.
  bot_thread = Thread(target=bot.polling, daemon=True)
  bot_thread.start()

  main()
