# tasks.py
import random

TASKS = [
    "Сделать 20 отжиманий",
    "Пробежать 1 километр",
    "Сделать 50 приседаний",
    "Выучить 5 новых слов",
    "Прочитать 10 страниц книги",
]

def generate_daily_task():
    return random.choice(TASKS)
