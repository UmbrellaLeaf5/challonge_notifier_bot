import json
from typing import Any

Config = dict[str, Any]

# MEANS: имя файла конфигурации.
config_file_name: str = (
  "config_real.json"  # предполагается, что файл config_template.json изменять не стоит
)

# MEANS: путь к файлу конфигурации.
main_config_file_name: str = f"config/{config_file_name}"


def GetConfig(file_name: str = main_config_file_name, encoding: str = "utf-8") -> Config:
  """
  Загружает конфигурацию из JSON-файла.

  Args:
      file_name (str): имя файла конфигурации.
      encoding (str): кодировка файла.

  Returns:
      Config: словарь с параметрами конфигурации.
  """

  # открываем файл конфигурации.
  with open(file_name, "r", encoding=encoding) as config:
    # загружаем конфигурацию из JSON.
    return json.load(config)


# MEANS: словарь, содержащий параметры конфигурации.
config = GetConfig()
