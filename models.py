"""
로또 예측 성능 분석 대시보드 - 데이터 모델 & 분석 엔진
"""

import sqlite3
import os
import json
import random
import numpy as np
from datetime import datetime
from collections import Counter

DB_PATH = os.environ.get('DATABASE_PATH', 
    '/opt/render/project/data/lotto_dashboard.db' if os.path.exists('/opt/render/project/data') 
    else 'lotto_dashboard.db'
)

# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 코드 정보 (7개 코드)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
CODES = {
    '2601': {'name': 'The strongest in the universe ver3.0', 'sets': 5,  'color': '#EF4444', 'short': 'ULT'},
    '2602': {'name': 'Lotto-ultimate-v3.0',  'sets': 5,  'color': '#3B82F6', 'short': 'QTM'},
    '2603': {'name': 'Lotto-ultimate-v1.5', 'sets': 5,  'color': '#10B981', 'short': 'MOM'},
    '2604': {'name': 'Super v2.0 Feature Engineering',     'sets': 5,  'color': '#8B5CF6', 'short': 'DEP'},
    '2605': {'name': 'The strongest in the universe v4.0',   'sets': 5,  'color': '#F59E0B', 'short': 'HYB'},
    '2606': {'name': 'Platinum Lotto System v5.0', 'sets': 5,  'color': '#EC4899', 'short': 'PLT'},
    '2607': {'name': 'Brother v2.0',  'sets': 21, 'color': '#F97316', 'short': 'BRO'},
}

LOTTO_ZONES = {
    '1~10':  list(range(1, 11)),
    '11~20': list(range(11, 21)),
    '21~30': list(range(21, 31)),
    '31~40': list(range(31, 41)),
    '41~45': list(range(41, 46)),
}


def get_db():
    """데이터베이스 연결"""
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db():
    """테이블 초기화"""
    conn = get_db()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS rounds (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_number INTEGER UNIQUE NOT NULL,
            draw_date TEXT,
            num1 INTEGER, num2 INTEGER, num3 INTEGER,
            num4 INTEGER, num5 INTEGER, num6 INTEGER,
            bonus INTEGER,
            created_at TEXT DEFAULT (datetime('now'))
        );

        CREATE TABLE IF NOT EXISTS predictions (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            code_id TEXT NOT NULL,
            set_number INTEGER NOT NULL,
            num1 INTEGER, num2 INTEGER, num3 INTEGER,
            num4 INTEGER, num5 INTEGER, num6 INTEGER,
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (round_id) REFERENCES rounds(id),
            UNIQUE(round_id, code_id, set_number)
        );

        CREATE TABLE IF NOT EXISTS random_baselines (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            round_id INTEGER NOT NULL,
            baseline_group TEXT NOT NULL,
            set_number INTEGER NOT NULL,
            num1 INTEGER, num2 INTEGER, num3 INTEGER,
            num4 INTEGER, num5 INTEGER, num6 INTEGER,
            FOREIGN KEY (round_id) REFERENCES rounds(id)
        );
    """)
    conn.commit()
    conn.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# CRUD 함수
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def save_round(round_number, draw_date, numbers, bonus=None):
    """회차 당첨 번호 저장"""
    conn = get_db()
    try:
        conn.execute(
            "INSERT OR REPLACE INTO rounds (round_number, draw_date, num1, num2, num3, num4, num5, num6, bonus) "
            "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)",
            (round_number, draw_date, *sorted(numbers), bonus)
        )
        conn.commit()
        row = conn.execute("SELECT id FROM rounds WHERE round_number=?", (round_number,)).fetchone()
        round_id = row['id']

        # 랜덤 기준선 자동 생성 (5세트 × 3그룹 + 21세트 × 1그룹)
        conn.execute("DELETE FROM random_baselines WHERE round_id=?", (round_id,))
        for group in ['rand5_A', 'rand5_B', 'rand5_C']:
            for s in range(5):
                nums = sorted(random.sample(range(1, 46), 6))
                conn.execute(
                    "INSERT INTO random_baselines (round_id, baseline_group, set_number, num1,num2,num3,num4,num5,num6) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (round_id, group, s + 1, *nums)
                )
        # 21세트 랜덤 (2607 비교용)
        for s in range(21):
            nums = sorted(random.sample(range(1, 46), 6))
            conn.execute(
                "INSERT INTO random_baselines (round_id, baseline_group, set_number, num1,num2,num3,num4,num5,num6) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (round_id, 'rand21', s + 1, *nums)
            )

        conn.commit()
        return round_id
    finally:
        conn.close()


def save_predictions(round_number, code_id, sets_list):
    """예측 번호 저장 (sets_list: [[n1,n2,...n6], ...])"""
    conn = get_db()
    try:
        row = conn.execute("SELECT id FROM rounds WHERE round_number=?", (round_number,)).fetchone()
        if not row:
            return False
        round_id = row['id']

        conn.execute("DELETE FROM predictions WHERE round_id=? AND code_id=?", (round_id, code_id))
        for i, nums in enumerate(sets_list):
            conn.execute(
                "INSERT INTO predictions (round_id, code_id, set_number, num1,num2,num3,num4,num5,num6) "
                "VALUES (?,?,?,?,?,?,?,?,?)",
                (round_id, code_id, i + 1, *sorted(nums))
            )
        conn.commit()
        return True
    finally:
        conn.close()


def get_all_rounds():
    """모든 회차 조회"""
    conn = get_db()
    rows = conn.execute("SELECT * FROM rounds ORDER BY round_number DESC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_round_data(round_number):
    """특정 회차의 전체 데이터"""
    conn = get_db()
    round_row = conn.execute("SELECT * FROM rounds WHERE round_number=?", (round_number,)).fetchone()
    if not round_row:
        conn.close()
        return None

    round_id = round_row['id']
    actual = [round_row[f'num{i}'] for i in range(1, 7)]

    predictions = {}
    for code_id in CODES:
        preds = conn.execute(
            "SELECT * FROM predictions WHERE round_id=? AND code_id=? ORDER BY set_number",
            (round_id, code_id)
        ).fetchall()
        if preds:
            predictions[code_id] = [[p[f'num{i}'] for i in range(1, 7)] for p in preds]

    baselines = {}
    for bl in conn.execute("SELECT * FROM random_baselines WHERE round_id=?", (round_id,)).fetchall():
        group = bl['baseline_group']
        if group not in baselines:
            baselines[group] = []
        baselines[group].append([bl[f'num{i}'] for i in range(1, 7)])

    conn.close()
    return {
        'round': dict(round_row),
        'actual': actual,
        'predictions': predictions,
        'baselines': baselines,
    }


def delete_round(round_number):
    """회차 삭제"""
    conn = get_db()
    row = conn.execute("SELECT id FROM rounds WHERE round_number=?", (round_number,)).fetchone()
    if row:
        rid = row['id']
        conn.execute("DELETE FROM predictions WHERE round_id=?", (rid,))
        conn.execute("DELETE FROM random_baselines WHERE round_id=?", (rid,))
        conn.execute("DELETE FROM rounds WHERE id=?", (rid,))
        conn.commit()
    conn.close()


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 분석 엔진
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
def compute_matches(actual, predicted_sets):
    """일치 수 계산"""
    actual_set = set(actual)
    return [len(actual_set & set(s)) for s in predicted_sets]


def get_code_performance(code_id):
    """특정 코드의 전체 성과 분석"""
    conn = get_db()
    rounds = conn.execute("SELECT * FROM rounds ORDER BY round_number ASC").fetchall()

    results = []
    for r in rounds:
        actual = [r[f'num{i}'] for i in range(1, 7)]
        preds = conn.execute(
            "SELECT * FROM predictions WHERE round_id=? AND code_id=? ORDER BY set_number",
            (r['id'], code_id)
        ).fetchall()
        if not preds:
            continue

        pred_sets = [[p[f'num{i}'] for i in range(1, 7)] for p in preds]
        matches = compute_matches(actual, pred_sets)

        results.append({
            'round_number': r['round_number'],
            'max_match': max(matches),
            'avg_match': sum(matches) / len(matches),
            'match_3plus': sum(1 for m in matches if m >= 3),
            'match_4plus': sum(1 for m in matches if m >= 4),
            'match_5plus': sum(1 for m in matches if m >= 5),
            'n_sets': len(pred_sets),
            'all_matches': matches,
        })

    conn.close()
    return results


def get_dashboard_data():
    """대시보드 전체 데이터 생성"""
    conn = get_db()
    rounds = conn.execute("SELECT * FROM rounds ORDER BY round_number ASC").fetchall()

    if not rounds:
        conn.close()
        return {
            'total_rounds': 0,
            'code_rankings': [],
            'round_labels': [],
            'performance_series': {},
            'random_series': {},
            'zone_heatmap': {},
        }

    # ── 1. 코드별 성과 집계 ──
    code_stats = {}
    round_labels = []
    performance_series = {}  # code_id → [max_match per round]
    random_series = {}       # group → [max_match per round]
    zone_heatmap = {}        # code_id → {zone: count}

    for code_id in CODES:
        code_stats[code_id] = {
            'total_rounds': 0,
            'total_max_matches': 0,
            'match_3plus': 0,
            'match_4plus': 0,
            'match_5plus': 0,
            'all_numbers': [],
        }
        performance_series[code_id] = []
        zone_heatmap[code_id] = {zone: 0 for zone in LOTTO_ZONES}

    for group in ['rand5_avg', 'rand21']:
        random_series[group] = []

    for r in rounds:
        round_number = r['round_number']
        round_labels.append(str(round_number))
        actual = [r[f'num{i}'] for i in range(1, 7)]
        actual_set = set(actual)
        round_id = r['id']

        # 각 코드 성과
        for code_id in CODES:
            preds = conn.execute(
                "SELECT * FROM predictions WHERE round_id=? AND code_id=? ORDER BY set_number",
                (round_id, code_id)
            ).fetchall()

            if preds:
                pred_sets = [[p[f'num{i}'] for i in range(1, 7)] for p in preds]
                matches = compute_matches(actual, pred_sets)
                max_m = max(matches)

                code_stats[code_id]['total_rounds'] += 1
                code_stats[code_id]['total_max_matches'] += max_m
                code_stats[code_id]['match_3plus'] += sum(1 for m in matches if m >= 3)
                code_stats[code_id]['match_4plus'] += sum(1 for m in matches if m >= 4)
                code_stats[code_id]['match_5plus'] += sum(1 for m in matches if m >= 5)
                performance_series[code_id].append(max_m)

                # 번호 대역별 카운트
                for nums in pred_sets:
                    for n in nums:
                        code_stats[code_id]['all_numbers'].append(n)
                        for zone_name, zone_nums in LOTTO_ZONES.items():
                            if n in zone_nums:
                                zone_heatmap[code_id][zone_name] += 1
            else:
                performance_series[code_id].append(None)

        # 랜덤 기준선
        rand5_maxes = []
        for group in ['rand5_A', 'rand5_B', 'rand5_C']:
            bl_rows = conn.execute(
                "SELECT * FROM random_baselines WHERE round_id=? AND baseline_group=?",
                (round_id, group)
            ).fetchall()
            if bl_rows:
                bl_sets = [[b[f'num{i}'] for i in range(1, 7)] for b in bl_rows]
                bl_matches = compute_matches(actual, bl_sets)
                rand5_maxes.append(max(bl_matches))

        random_series['rand5_avg'].append(
            round(sum(rand5_maxes) / len(rand5_maxes), 2) if rand5_maxes else None
        )

        bl21_rows = conn.execute(
            "SELECT * FROM random_baselines WHERE round_id=? AND baseline_group='rand21'",
            (round_id,)
        ).fetchall()
        if bl21_rows:
            bl21_sets = [[b[f'num{i}'] for i in range(1, 7)] for b in bl21_rows]
            bl21_matches = compute_matches(actual, bl21_sets)
            random_series['rand21'].append(max(bl21_matches))
        else:
            random_series['rand21'].append(None)

    conn.close()

    # ── 2. 랭킹 계산 ──
    rankings = []
    for code_id, stats in code_stats.items():
        n = stats['total_rounds']
        if n == 0:
            continue
        avg_max = stats['total_max_matches'] / n
        pct_3plus = stats['match_3plus'] / n * 100 if n > 0 else 0

        # 랜덤 대비 향상율
        rand_key = 'rand21' if CODES[code_id]['sets'] == 21 else 'rand5_avg'
        rand_vals = [v for v in random_series[rand_key] if v is not None]
        rand_avg = sum(rand_vals) / len(rand_vals) if rand_vals else 1
        improvement = ((avg_max - rand_avg) / rand_avg * 100) if rand_avg > 0 else 0

        rankings.append({
            'code_id': code_id,
            'name': CODES[code_id]['name'],
            'short': CODES[code_id]['short'],
            'color': CODES[code_id]['color'],
            'sets': CODES[code_id]['sets'],
            'rounds': n,
            'avg_max_match': round(avg_max, 2),
            'pct_3plus': round(pct_3plus, 1),
            'match_4plus': stats['match_4plus'],
            'match_5plus': stats['match_5plus'],
            'vs_random': round(improvement, 1),
        })

    # 랭킹 정렬: avg_max_match → pct_3plus → match_4plus
    rankings.sort(key=lambda x: (x['avg_max_match'], x['pct_3plus'], x['match_4plus']), reverse=True)
    for i, r in enumerate(rankings):
        r['rank'] = i + 1

    # ── 3. 번호 대역 히트맵 정규화 ──
    zone_heatmap_normalized = {}
    for code_id, zones in zone_heatmap.items():
        total = sum(zones.values())
        if total > 0:
            zone_heatmap_normalized[code_id] = {
                z: round(v / total * 100, 1) for z, v in zones.items()
            }
        else:
            zone_heatmap_normalized[code_id] = zones

    return {
        'total_rounds': len(rounds),
        'code_rankings': rankings,
        'round_labels': round_labels,
        'performance_series': performance_series,
        'random_series': random_series,
        'zone_heatmap': zone_heatmap_normalized,
    }


def get_round_detail_analysis(round_number):
    """특정 회차 상세 분석"""
    data = get_round_data(round_number)
    if not data:
        return None

    actual = data['actual']
    analysis = {'actual': actual, 'codes': {}}

    for code_id, pred_sets in data['predictions'].items():
        matches = compute_matches(actual, pred_sets)
        best_idx = matches.index(max(matches))

        # 번호별 적중 표시
        set_details = []
        for i, (s, m) in enumerate(zip(pred_sets, matches)):
            hits = sorted(set(actual) & set(s))
            set_details.append({
                'numbers': s,
                'match_count': m,
                'hit_numbers': hits,
                'is_best': i == best_idx,
            })

        analysis['codes'][code_id] = {
            'name': CODES[code_id]['name'],
            'color': CODES[code_id]['color'],
            'max_match': max(matches),
            'avg_match': round(sum(matches) / len(matches), 2),
            'sets': set_details,
        }

    return analysis
