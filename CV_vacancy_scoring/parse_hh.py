from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple
from bs4 import BeautifulSoup

def parse_cv(html: str) -> str:
    """
    Парсит HTML страницы резюме (формат hh.ru) и возвращает Markdown-выжимку по кандидату.

    """

    soup = BeautifulSoup(html, "html.parser")

    def clean(text: Optional[str]) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def sel_text(css: str) -> str:
        el = soup.select_one(css)
        return clean(el.get_text(" ", strip=True) if el else "")

    # --- 1) Достаём то, что обычно стабильно лежит в DOM по data-qa ---
    position = sel_text('[data-qa="resume-block-title-position"]')
    # Метро/локация (иногда есть address, иногда metro)
    metro = sel_text('[data-qa="resume-personal-metro"]')
    address = (
        sel_text('[data-qa="resume-personal-address"]')
        or sel_text('[data-qa="resume-personal-address"] span')
    )
    location = clean(", ".join([x for x in [address, metro] if x]))

    # "Обо мне" / "О себе" (в этом HTML встречается именно так)
    about = sel_text('[data-qa="resume-block-skills-content"]')

    # --- 2) Достаём структурированные данные из встроенного JSON в HTML ---
    # В hh-страницах часто есть крупный JSON-объект/кусок со словами:
    # "advancedKeySkills": {"value":[...]} , "experience": {"value":[...]} и т.д.
    def extract_balanced_json_after_marker(
        text: str, marker: str, open_char: str, close_char: str
    ) -> Optional[str]:
        """
        Находит marker, затем первый open_char после него и вырезает сбалансированный JSON-блок,
        учитывая строки и escape-последовательности.
        """
        i = text.find(marker)
        if i == -1:
            return None
        i = text.find(open_char, i)
        if i == -1:
            return None

        depth = 0
        in_str = False
        esc = False
        start = i

        for j in range(i, len(text)):
            ch = text[j]

            if in_str:
                if esc:
                    esc = False
                elif ch == "\\":
                    esc = True
                elif ch == '"':
                    in_str = False
                continue

            # вне строки
            if ch == '"':
                in_str = True
                continue

            if ch == open_char:
                depth += 1
            elif ch == close_char:
                depth -= 1
                if depth == 0:
                    return text[start : j + 1]

        return None

    def extract_value_array(marker: str) -> Optional[List[Any]]:
        block = extract_balanced_json_after_marker(
            html, marker=marker, open_char="[", close_char="]"
        )
        if not block:
            return None
        try:
            return json.loads(block)
        except Exception:
            return None

    def extract_value_object(marker: str) -> Optional[Dict[str, Any]]:
        block = extract_balanced_json_after_marker(
            html, marker=marker, open_char="{", close_char="}"
        )
        if not block:
            return None
        try:
            return json.loads(block)
        except Exception:
            return None

    # Навыки: advancedKeySkills.value = [{id, name, general}, ...]
    skills_items = extract_value_array('"advancedKeySkills":{"value":') or []
    skills = [clean(x.get("name")) for x in skills_items if isinstance(x, dict) and x.get("name")]
    # Опыт: experience.value = [{companyName, position, start, end, description, ...}, ...]
    exp_items = extract_value_array('"experience":{"value":') or []
    # Образование: education.value = [...]
    edu_items = extract_value_array('"education":{"value":') or []

    # Если "position" не нашли в DOM — иногда она есть и в JSON (ищем грубо)
    if not position:
        # Популярный ключ у HH менялся, поэтому ищем по нескольким маркерам
        for mk in ('"title":{"value":', '"desiredPosition":{"value":', '"position":{"value":'):
            obj = extract_value_object(mk)
            if isinstance(obj, dict):
                v = obj.get("value")
                if isinstance(v, str) and clean(v):
                    position = clean(v)
                    break

    # --- 3) Формируем Markdown ---
    lines: List[str] = []

    header = position or "Кандидат"
    lines.append(f"# {header}")

    if location:
        lines.append(f"- **Локация:** {location}")

    # --- About ---
    if about:
        lines.append("")
        lines.append("## Обо мне")
        lines.append(about)

    # --- Skills ---
    if skills:
        lines.append("")
        lines.append("## Ключевые навыки")
        for s in skills:
            lines.append(f"- {s}")

    # --- Experience ---
    if exp_items:
        lines.append("")
        lines.append("## Опыт работы")

        for item in exp_items:
            if not isinstance(item, dict):
                continue
            company = clean(item.get("companyName") or "")
            role = clean(item.get("position") or item.get("jobTitle") or "")
            start = clean(item.get("start") or item.get("startDate") or "")
            end = clean(item.get("end") or item.get("endDate") or "")
            period = " — ".join([x for x in [start, end] if x]) if (start or end) else ""

            title_bits = [b for b in [company, role] if b]
            title = " — ".join(title_bits) if title_bits else "Место работы"
            if period:
                lines.append(f"### {title} ({period})")
            else:
                lines.append(f"### {title}")

            desc = item.get("description")
            if isinstance(desc, str) and clean(desc):
                # Превращаем маркеры "- " в списки, остальное оставляем текстом
                desc_lines = [x.rstrip() for x in desc.splitlines()]
                bullets = [clean(x[1:]) for x in desc_lines if x.lstrip().startswith("-")]
                plain = clean("\n".join([x for x in desc_lines if not x.lstrip().startswith("-")]))
                if plain:
                    lines.append(plain)
                if bullets:
                    for b in bullets:
                        if b:
                            lines.append(f"- {b}")
            lines.append("")

    # --- Education ---
    if edu_items:
        lines.append("")
        lines.append("## Образование")

        for item in edu_items:
            if not isinstance(item, dict):
                continue
            year = clean(str(item.get("year") or ""))
            org = clean(item.get("organization") or item.get("universityName") or "")
            result = clean(item.get("result") or item.get("faculty") or "")
            specialty = clean(item.get("specialty") or "")

            parts = [p for p in [org, result, specialty] if p]
            line = " — ".join(parts) if parts else ""
            if year and line:
                lines.append(f"- **{year}**: {line}")
            elif line:
                lines.append(f"- {line}")

    md = "\n".join([l.rstrip() for l in lines]).strip() + "\n"
    return md





def parse_vac(html: str) -> str:
    """
    Парсит HTML страницы вакансии (hh.ru) и возвращает Markdown-выжимку по вакансии.

    """

    soup = BeautifulSoup(html, "html.parser")

    def clean(text: Optional[str]) -> str:
        if not text:
            return ""
        return re.sub(r"\s+", " ", text).strip()

    def sel_text(css: str) -> str:
        el = soup.select_one(css)
        if not el:
            return ""
        return clean(el.get_text(" ", strip=True))

    def meta(name: Optional[str] = None, prop: Optional[str] = None) -> str:
        if name:
            tag = soup.find("meta", attrs={"name": name})
        else:
            tag = soup.find("meta", attrs={"property": prop}) if prop else None
        return clean(tag.get("content") if tag else "")

    def parse_from_meta_description(desc: str) -> Tuple[str, str, str, str]:
        """
        Из meta description hh часто можно достать:
        - город
        - требуемый опыт
        - занятость
        - дату публикации
        Пример формата (как в твоём HTML):
        "... Зарплата: ... Москва. Требуемый опыт: 3–6 лет. Полная. Дата публикации: 23.01.2026."
        """
        city = ""
        exp = ""
        employment = ""
        pub = ""

        # Город — часто отдельным предложением "Москва."
        # Берём первое "слово." после "Зарплата:" / "компании ..." — грубо, но полезно как fallback.
        m_city = re.search(r"Зарплата:.*?\.\s*([А-ЯA-ZЁ][^\.]{1,80})\.", desc)
        if m_city:
            city = clean(m_city.group(1))

        m_exp = re.search(r"Требуемый опыт:\s*([^\.]+)\.", desc)
        if m_exp:
            exp = clean(m_exp.group(1))

        # Занятость/формат ("Полная.", "Частичная.", ...)
        m_emp = re.search(r"Требуемый опыт:.*?\.\s*([^\.]+)\.\s*Дата публикации:", desc)
        if m_emp:
            employment = clean(m_emp.group(1))

        m_pub = re.search(r"Дата публикации:\s*([^\.]+)\.", desc)
        if m_pub:
            pub = clean(m_pub.group(1))

        return city, exp, employment, pub

    # --- Базовые поля из DOM (data-qa), с запасными вариантами ---
    title = (
        sel_text('[data-qa="vacancy-title"]')
        or sel_text("h1")
        or clean(soup.title.get_text(" ", strip=True) if soup.title else "")
    )

    company = (
        sel_text('[data-qa="vacancy-company-name"]')
        or sel_text('[data-qa="vacancy-company-name"] a')
        or sel_text('[data-qa="vacancy-company"]')
    )

    salary = (
        sel_text('[data-qa="vacancy-salary"]')
        or sel_text('[data-qa="vacancy-salary-compensation-type-net"]')
        or sel_text('[data-qa="vacancy-salary-compensation-type-gross"]')
    )

    experience = sel_text('[data-qa="vacancy-experience"]')
    employment = sel_text('[data-qa="vacancy-employment-mode"]') or sel_text('[data-qa="vacancy-employment"]')
    schedule = sel_text('[data-qa="vacancy-work-schedule"]') or sel_text('[data-qa="vacancy-schedule"]')

    # Локация/адрес
    area = sel_text('[data-qa="vacancy-view-location"]') or sel_text('[data-qa="vacancy-view-raw-address"]')
    metro = sel_text('[data-qa="vacancy-view-metro"]')
    location = clean(", ".join([x for x in [area, metro] if x]))

    # Дата публикации: в DOM бывает по-разному, поэтому fallback на meta description
    published = sel_text('[data-qa="vacancy-creation-time"]') or sel_text('[data-qa="vacancy-publication-time"]')

    # Описание вакансии
    desc_block = soup.select_one('[data-qa="vacancy-description"]') or soup.select_one('[data-qa="vacancy-description-container"]')
    description = ""
    if desc_block:
        # Сохраняем переносы строк чуть аккуратнее
        description = desc_block.get_text("\n", strip=True)
        description = re.sub(r"\n{3,}", "\n\n", description).strip()

    # Ключевые навыки (теги)
    skills: List[str] = []
    # Часто внутри есть теги bloko-tag__text
    for el in soup.select('[data-qa="bloko-tag__text"], [data-qa="vacancy-skill"] [data-qa="bloko-tag__text"]'):
        t = clean(el.get_text(" ", strip=True))
        if t and t not in skills:
            skills.append(t)

    # --- Fallback из meta description (в твоём HTML это прям очень полезно) ---
    meta_desc = meta(name="description")
    meta_city, meta_exp, meta_employment, meta_pub = parse_from_meta_description(meta_desc)

    if not experience:
        experience = meta_exp
    if not employment:
        employment = meta_employment
    if not published:
        published = meta_pub
    if not location and meta_city:
        location = meta_city

    # canonical + vacancy id (приятно иметь)
    canonical = ""
    vac_id = ""
    link = soup.find("link", attrs={"rel": "canonical"})
    if link and link.get("href"):
        canonical = clean(link["href"])
        m = re.search(r"/vacancy/(\d+)", canonical)
        if m:
            vac_id = m.group(1)

    # --- Markdown сборка ---
    lines: List[str] = []
    lines.append(f"# {title or 'Вакансия'}")

    # шапка-атрибуты
    if company:
        lines.append(f"- **Компания:** {company}")
    if salary:
        lines.append(f"- **Зарплата:** {salary}")
    if location:
        lines.append(f"- **Локация:** {location}")
    if experience:
        lines.append(f"- **Опыт:** {experience}")
    if employment:
        lines.append(f"- **Занятость:** {employment}")
    if schedule:
        lines.append(f"- **График:** {schedule}")
    if published:
        lines.append(f"- **Опубликовано:** {published}")
    if vac_id:
        lines.append(f"- **Vacancy ID:** {vac_id}")
    if canonical:
        lines.append(f"- **Ссылка:** {canonical}")

    # навыки
    if skills:
        lines.append("")
        lines.append("## Ключевые навыки")
        for s in skills:
            lines.append(f"- {s}")

    # описание
    if description:
        lines.append("")
        lines.append("## Описание")
        lines.append(description)

    return "\n".join(lines).rstrip() + "\n"
