import telebot
import requests
import time

from config.config import config


bot = telebot.TeleBot(config["tg_bot_token"])

# Already notified matches
notified_matches = set()


@bot.message_handler(commands=["start"])
def Start(message):
  bot.reply_to(
    message,
    "🥃 Добро пожаловать на турнир по бирпонгу 2025!"
    "\n Для просмотра объявлений о проведении матчей перейдите в чат: "
    f"https://t.me/{bot.get_chat(config['tg_chat_id']).username} 🍻",
  )


def FetchMatches():
  """
  Get all matches from the tournament.
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
  return response.json()


def NotifyMatches():
  """
  Check the match status and send notifications.
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


def FetchParticipantName(participant_id):
  """
  Get the team name.
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
  while True:
    NotifyMatches()
    time.sleep(15)  # Fetch every 15 seconds


if __name__ == "__main__":
  from threading import Thread

  bot_thread = Thread(target=bot.polling, args=())
  bot_thread.start()

  main()
