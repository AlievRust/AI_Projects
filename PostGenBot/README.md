# Генератор постов для ТГ:
## заданная тема + новости CurrentsAPI + генерация названия/метаинформации/поста для ТГ + картинка с цитатой (оверлей) на Stability AI => вывод в ТГ-бота

Бэкенд в части запросов и генерации задумывался для деплоя на стороннем сервере (render.com), логика - Zapier (или аналог)

Скрин процесса в Zapier:
<img width="428" height="788" alt="example_scr_zapier" src="https://github.com/user-attachments/assets/d9ac9ab4-71af-4ff2-8a29-3cb36d7ac734" />

Скрины постов (первый - картинка+краткое содержание, второй - основная статья)
<img width="461" height="683" alt="example_scr_tg_img_w_caption" src="https://github.com/user-attachments/assets/dea205e3-5dbe-4fb4-97c6-b82b05a65d7d" />
<img width="483" height="752" alt="example_scr_tg_main_post" src="https://github.com/user-attachments/assets/9a29bb9d-a3fe-46f5-9be6-d1b7a2c541a1" />

* Допиливая основной запрос и регулируя количество токенов в параметрах, можно менять размер основной статьи, её структуру и т.п.
* Данный воркфлоу использует API StabilityAI, при необходимости легко внедряется любая модель с поддержкой API (Yandex ART, OpenAI и т.п.)

