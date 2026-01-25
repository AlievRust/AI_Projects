from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

import streamlit as st
from dotenv import load_dotenv
import os
from openai import OpenAI

# грузим библиотеки из соседних файлов
from get_html import get_html
from parse_hh import parse_cv, parse_vac

load_dotenv()

OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY")

scoring_prompt = """
                    Оцени кандидата, насколько он подходит для данной вакансии.
                    Сначала напиши короткий анализ, который будет пояснять оценку.
                    Отдельно оцени качество заполнения резюме (понятно ли, с какими задачами сталкивался кандидат и каким образом их решал?). Эта оценка должна учитываться при выставлении финальной оценки - нам важно нанимать таких кандидатов, которые могут рассказать про свою работу
                    Потом представь результат в виде оценки от 1 до 10.
                """.strip()

client = OpenAI(api_key=OPENAI_API_KEY)

def request_gpt(system_prompt, user_prompt):
    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": system_prompt},  
            {"role": "user", "content": user_prompt},     
        ],
        max_tokens=600,
        temperature=0,
    )
    return response.choices[0].message.content.strip()


# основная часть страницы приложения
st.title('CV Scoring App')

# два поля для ввода данных
vac = st.text_area('Введите URL вакансии')
cv = st.text_area('Введите URL резюме')



# кнопка и реакция на неё
if st.button('Оценка резюме'):
    with st.spinner('Анализирую...'):
        # Формирование пользовательского промпта
        html_cv = get_html(cv)
        if html_cv:
            cv_description = parse_cv(html_cv)
        else:
            cv_description = "Резюме не удалось прочитать"
        
        html_vac = get_html(vac)
        if html_vac:
            vac_description = parse_vac(html_vac)
        else:
            vac_description = "Вакансию не удалось прочитать"

        user_prompt = f"# ВАКАНСИЯ:\n{vac_description}\n\n# РЕЗЮМЕ:\n{cv_description}"
        response = request_gpt(scoring_prompt, user_prompt)
    st.write(response)
