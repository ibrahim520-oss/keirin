from flask import Flask, render_template_string
import requests
from bs4 import BeautifulSoup
import datetime
from concurrent.futures import ThreadPoolExecutor

app = Flask(__name__)

def get_today_date():
    return datetime.datetime.now().strftime('%Y%m%d')

def fetch_page(url):
    response = requests.get(url)
    return BeautifulSoup(response.text, 'html.parser')

def parse_deadline(deadline_str):
    try:
        return datetime.datetime.strptime(deadline_str, '%H:%M').time()
    except ValueError:
        return None

def extract_race_info(soup):
    rc_data_div = soup.find('div', id='RCdata2')
    tx_red_spans = soup.find_all('span', class_='tx_red')
    race_name_tag = soup.find('title')

    if rc_data_div:
        tx_red_span = rc_data_div.find('span', class_='tx_red')
    else:
        tx_red_span = None

    race_name = race_name_tag.get_text(strip=True) if race_name_tag else ""
    title_contains_keyword = 'Ｌ級ガ' in race_name
    valid_values = ['1.0', '1.1', '1.2', '1.3', '1.4']

    for span in tx_red_spans:
        span_text = span.get_text(strip=True)

        if '1.0' in span_text:
            if tx_red_span and '締切予定' in tx_red_span.get_text(strip=True):
                deadline_tag = tx_red_span.find_next('strong')
                if deadline_tag:
                    deadline = deadline_tag.get_text(strip=True)
                    return race_name, deadline

        if title_contains_keyword and any(value in span_text for value in valid_values[1:]):
            if tx_red_span and '締切予定' in tx_red_span.get_text(strip=True):
                deadline_tag = tx_red_span.find_next('strong')
                if deadline_tag:
                    deadline = deadline_tag.get_text(strip=True)
                    return race_name, deadline

    return None, None

def fetch_and_check_race(jo_code, today):
    for n in range(1, 13):
        url = f"https://www.oddspark.com/keirin/Odds.do?joCode={jo_code}&kaisaiBi={today}&raceNo={n}&betType=5"
        soup = fetch_page(url)
        race_name, deadline_str = extract_race_info(soup)
        if race_name and deadline_str:
            return (race_name, deadline_str)
    return None

def process_races(jo_codes, today):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = [executor.submit(fetch_and_check_race, code, today) for code in jo_codes]
        for future in futures:
            result = future.result()
            if result:
                results.append(result)
    return results

@app.route('/')
def index():
    today = get_today_date()
    jo_codes = [12, 13, 22, 23, 24, 25, 26, 27, 28, 34, 35, 37, 38, 42, 43, 44, 45, 47, 48, 51, 53, 55, 56, 63, 71, 73, 74, 75, 81, 83, 84, 85, 86, 87]
    results = process_races(jo_codes, today)

    html = """
    <h1>本日の対象レース一覧（{{ count }} 件）</h1>
    <ul>
    {% for name, deadline in results %}
        <li><strong>{{ name }}</strong> - 締切：{{ deadline }}</li>
    {% endfor %}
    </ul>
    """
    return render_template_string(html, results=results, count=len(results))

if __name__ == '__main__':
    app.run(debug=True)
