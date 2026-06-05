import io
import time

import requests
import telebot
from playwright.sync_api import sync_playwright

from config.config import config


# MEANS: экземпляр класса бота
bot = telebot.TeleBot(config["tg_bot_token"])

# MEANS: уже объявленные матчи
notified_matches = set()


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
  bot.send_photo(message.chat.id, image, caption="🧊 Актуальная турнирная сетка")


def FetchTournamentImage():
  """
  Скачивает SVG турнирной сетки и рендерит в PNG через Playwright.

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

  html = f'<html><body style="margin:0;background:#fff">{svg_response.text}</body></html>'

  with sync_playwright() as p:
    with p.chromium.launch() as browser:
      page = browser.new_page()

      page.set_content(html)

      screenshot = page.locator("svg#top_level").screenshot(type="png")

  return io.BytesIO(screenshot)


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

  print(response.json())

  return response.json()


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

      message = (
        f"🎉 <b>{winner}</b> — триумфатор матча\n{player_1} <i>vs</i> {player_2}! 🍻"
      )

      bot.send_message(config["tg_chat_id"], message, parse_mode="HTML")
      notified_matches.remove(match_id)

    if state == "open" and is_underway and match_id not in notified_matches:
      player_1 = FetchParticipantName(player_1_id)
      player_2 = FetchParticipantName(player_2_id)

      message = f"⚡️ Начинается матч:\n<b>{player_1}</b> – <b>{player_2}</b> 🍺"

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
  participant = response.json()

  return participant["participant"]["name"]


def main():
  """
  Основной цикл программы: проверяет матчи каждые 15 секунд.
  """

  while True:
    NotifyMatches()
    time.sleep(15)  # Fetch every 15 seconds


if __name__ == "__main__":
  from threading import Thread

  # MEANS: поток для работы бота.
  bot_thread = Thread(target=bot.polling, args=())
  bot_thread.start()

  main()
