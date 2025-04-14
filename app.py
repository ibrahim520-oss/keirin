from flask import Flask, render_template_string
from concurrent.futures import ThreadPoolExecutor
import requests
from bs4 import BeautifulSoup
import datetime
import time
import re

app = Flask(__name__)
cache = {}
CACHE_DURATION = 60  # キャッシュ有効期間（秒）

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

    # タイトル整形処理（「【オッズ】」と「｜競輪（KEIRIN）ならオッズパーク競輪」を削除）
    race_name = re.sub(r'^【オッズ】', '', race_name)
    race_name = re.sub(r'｜競輪（KEIRIN）ならオッズパーク競輪$', '', race_name).strip()
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

# 並列処理用：1レース処理
def process_single_race(args):
    jo_code, today = args
    for n in range(1, 13):
        url = f"https://www.oddspark.com/keirin/Odds.do?joCode={jo_code}&kaisaiBi={today}&raceNo={n}&betType=5"
        soup = fetch_page(url)
        race_name, deadline_str = extract_race_info(soup)
        if race_name and deadline_str:
            return (race_name, deadline_str)
    return None

# 並列に全レース処理
def process_races(jo_codes, today):
    results = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        args = [(jo_code, today) for jo_code in jo_codes]
        for result in executor.map(process_single_race, args):
            if result:
                results.append(result)
    return results

@app.route('/')
def index():
    return render_template_string("""
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>読み込み中</title>
        <script>
            // 3秒後に自動で /results に移動
            setTimeout(() => {
                window.location.href = "/results";
            }, 3000);
        </script>
        <style>
            body { font-family: sans-serif; text-align: center; margin-top: 100px; }
        </style>
    </head>
    <body>
        <h2>🔍 本日の対象レースを検索しています...</h2>
        <h3>対象レース</h3>
                                <p>         
                                 ・2車複、ワイドのオッズがともに1.0<br>
                                 ・レディース戦で2車複のオッズが1.4以下かつワイドオッズが1.0                      
                                </p> 

            <br><br><br><br>
            <p>※ネットの競輪投票サービスのキャンペーン利用すれば、無料登録だけでお金がもらえてかなりお得です！</p>

            <table border="1" cellpadding="8" cellspacing="0" style="margin: 0 auto; border-collapse: collapse; text-align: center;">
                <thead style="background-color: #f2f2f2;">
                    <tr>
                        <th>サービス名</th>
                        <th>キャンペーン特典</th>
                        <th>記事詳細</th>
                    </tr>
                </thead>
                <tbody>
                    <tr>
                        <td>ウィンチケット</td>
                        <td>最大8,100円</td>
                        <td><a href="https://x.gd/eY7Ve" target="_blank">記事を見る</a></td>
                    </tr>
                    <tr>
                        <td>オッズパーク</td>
                        <td>最大13,500円</td> 	
                        <td><a href="https://x.gd/vTyBf" target="_blank">記事を見る</a></td>
                    </tr>
                    <tr>
                        <td>DMM競輪</td>
                        <td>最大3,000円</td>
                        <td><a href="https://x.gd/Sy8iD" target="_blank">記事を見る</a></td>
                    </tr>
                    <tr>
                        <td>TIPSTAR</td>
                        <td>最大51,000円</td>
                        <td><a href="https://x.gd/ETnlp" target="_blank">記事を見る</a></td>
                    </tr>
                    <tr>
                        <td>チャリロト</td>
                        <td>最大4,000円</td>
                        <td><a href="https://x.gd/TQQ5L" target="_blank">記事を見る</a></td>
                    </tr>
                </tbody>
            </table>

            <p style="margin-top: 10px;">公営競技投票サービスのキャンペーン</p>                         
                                  
    </body>
    </html>
    """)

@app.route('/results')
def show_results():
    today = get_today_date()
    now = time.time()

    # キャッシュ確認
    if 'data' in cache and now - cache['timestamp'] < CACHE_DURATION:
        results = cache['data']
    else:
        jo_codes = [12, 13, 22, 23, 24, 25, 26, 27, 28, 34, 35, 37, 38, 42, 43, 44, 45, 47, 48, 51, 53, 55, 56, 63, 71, 73, 74, 75, 81, 83, 84, 85, 86, 87]
        results = process_races(jo_codes, today)
        cache['data'] = results
        cache['timestamp'] = now

    html = """
    <!DOCTYPE html>
    <html lang="ja">
    <head>
        <meta charset="UTF-8">
        <title>本日の対象レース</title>
    </head>
    <body>
        <h1>本日の対象レース一覧（{{ count }} 件）</h1>
        <ul>
        {% for name, deadline in results %}
            <li><strong>{{ name }}</strong> - 締切：{{ deadline }}</li>
        {% endfor %}
        </ul>
        <a href="/">🔄 もう一度読み込み</a>
        <br><br><br><br>
        <p>※ネットの競輪投票サービスのキャンペーン利用すれば、無料登録だけでお金がもらえてかなりお得です！</p>

        <table border="1" cellpadding="8" cellspacing="0">
            <thead>
                <tr>
                    <th>サービス名</th>
                    <th>キャンペーン特典</th>
                    <th>記事詳細</th>
                </tr>
            </thead>
            <tbody>
                <tr>
                    <td>ウィンチケット</td>
                    <td>最大8,100円</td>
                    <td><a href="https://x.gd/eY7Ve" target="_blank">記事を見る</a></td>
                </tr>
                <tr>
                    <td>オッズパーク</td>
                    <td>最大13,500円</td> 	
                    <td><a href="https://x.gd/vTyBf" target="_blank">記事を見る</a></td>
                </tr>
                <tr>
                    <td>DMM競輪</td>
                    <td>最大3,000円</td>
                    <td><a href="https://x.gd/Sy8iD" target="_blank">記事を見る</a></td>
                </tr>
                <tr>
                    <td>TIPSTAR</td>
                    <td>最大51,000円</td>
                    <td><a href="https://x.gd/ETnlp" target="_blank">記事を見る</a></td>
                </tr>
                <tr>
                    <td>チャリロト</td>
                    <td>最大4,000円</td>
                    <td><a href="https://x.gd/TQQ5L" target="_blank">記事を見る</a></td>
                </tr>
            </tbody>
        </table>

        <p style="margin-top: 10px;">公営競技投票サービスのキャンペーン</p>
    </body>
    </html>
    """
    return render_template_string(html, results=results, count=len(results))

if __name__ == '__main__':
    app.run(debug=True)
