import telebot
import requests
import time

# Conf
TOKEN = "<TELEGRAM_BOT_TOKEN>"
CHALLONGE_API_KEY = "<CHALLONGE_API_KEY>"
TOURNAMENT_URL = "<TOURNAMENT_ID>"  # ID of the tournament, for example 'mytournament' in 'https://challonge.com/mytournament'
CHAT_ID = "<CHAT_ID>"  # Chat to send messages to
COOKIES = {"<place cookies here for connection>"}


bot = telebot.TeleBot(TOKEN)

# Already notified matches
notified_matches = set()


@bot.message_handler(commands=["start"])
def start(message):
  bot.reply_to(message, "Bot is running!")


def fetch_matches():
  """get all matches from the tournament"""
  url = f"https://api.challonge.com/v1/tournaments/{TOURNAMENT_URL}/matches.json"
  params = {"api_key": CHALLONGE_API_KEY}
  headers = COOKIES
  response = requests.get(url, params=params, headers=headers)
  response.raise_for_status()
  return response.json()


def notify_matches():
  """check the match status and send notifications"""
  matches = fetch_matches()
  for match in matches:
    match_id = match["match"]["id"]
    player1_id = match["match"]["player1_id"]
    player2_id = match["match"]["player2_id"]
    state = match["match"]["state"]
    is_underway = match["match"]["underway_at"]

    if state == "complete" and match_id in notified_matches:
      player1 = fetch_participant_name(player1_id)
      player2 = fetch_participant_name(player2_id)
      winner = fetch_participant_name(match["match"]["winner_id"])
      message = (
        f"🎉 <b>{winner}</b> — триумфатор матча\n{player1} <i>vs</i> {player2}! 🍻"
      )
      bot.send_message(CHAT_ID, message, parse_mode="HTML")
      notified_matches.remove(match_id)

    if state == "open" and is_underway and match_id not in notified_matches:
      player1 = fetch_participant_name(player1_id)
      player2 = fetch_participant_name(player2_id)
      message = f"⚡️ Начинается матч:\n<b>{player1}</b> – <b>{player2}</b> 🍺"
      bot.send_message(CHAT_ID, message, parse_mode="HTML")
      notified_matches.add(match_id)


def fetch_participant_name(participant_id="233472101"):
  """get the team name"""
  url = f"https://api.challonge.com/v1/tournaments/{TOURNAMENT_URL}/participants/{participant_id}.json"
  params = {"api_key": CHALLONGE_API_KEY}
  headers = COOKIES
  response = requests.get(url, params=params, headers=headers)
  participant = response.json()
  return participant["participant"]["name"]


def main():
  while True:
    notify_matches()
    time.sleep(15)  # Fetch every 15 seconds


if __name__ == "__main__":
  from threading import Thread

  bot_thread = Thread(target=bot.polling, args=())
  bot_thread.start()
  main()
