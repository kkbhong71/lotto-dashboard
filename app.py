"""
로또 예측 성능 분석 대시보드 - Flask Web Application
"""
from flask import Flask, render_template, request, redirect, url_for, jsonify, flash
import json, os
from models import (
    init_db, CODES, save_round, save_predictions, get_all_rounds,
    get_round_data, delete_round, get_dashboard_data, get_round_detail_analysis,
)

app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'lotto-dashboard-dev-key-2025')

with app.app_context():
    init_db()

@app.route('/')
def dashboard():
    data = get_dashboard_data()
    return render_template('dashboard.html', data=data, codes=CODES,
                           data_json=json.dumps(data, ensure_ascii=False))

@app.route('/input', methods=['GET'])
def input_page():
    rounds = get_all_rounds()
    return render_template('input.html', codes=CODES, rounds=rounds)

@app.route('/input/round', methods=['POST'])
def save_round_data():
    try:
        round_number = int(request.form['round_number'])
        draw_date = request.form.get('draw_date', '')
        numbers = []
        for i in range(1, 7):
            n = int(request.form[f'actual_num{i}'])
            if not (1 <= n <= 45):
                flash(f'번호 {n}은(는) 1~45 범위를 벗어났습니다.', 'error')
                return redirect(url_for('input_page'))
            numbers.append(n)
        if len(set(numbers)) != 6:
            flash('중복된 번호가 있습니다.', 'error')
            return redirect(url_for('input_page'))
        bonus = request.form.get('bonus')
        bonus = int(bonus) if bonus and bonus.strip() else None
        save_round(round_number, draw_date, numbers, bonus)
        flash(f'{round_number}회차 당첨 번호가 저장되었습니다.', 'success')
    except (ValueError, KeyError) as e:
        flash(f'입력 오류: {e}', 'error')
    return redirect(url_for('input_page'))

@app.route('/input/predictions', methods=['POST'])
def save_prediction_data():
    try:
        round_number = int(request.form['pred_round_number'])
        code_id = request.form['code_id']
        if code_id not in CODES:
            flash(f'알 수 없는 코드: {code_id}', 'error')
            return redirect(url_for('input_page'))
        raw_text = request.form.get('prediction_text', '').strip()
        if not raw_text:
            flash('예측 번호를 입력해주세요.', 'error')
            return redirect(url_for('input_page'))
        sets_list = []
        for line in raw_text.strip().split('\n'):
            line = line.strip()
            if not line:
                continue
            nums = []
            for part in line.replace(',', ' ').replace('\t', ' ').split():
                part = part.strip()
                if part.isdigit():
                    nums.append(int(part))
            if len(nums) == 6 and all(1 <= n <= 45 for n in nums):
                sets_list.append(sorted(nums))
        if len(sets_list) == 0:
            flash('유효한 세트가 없습니다.', 'error')
            return redirect(url_for('input_page'))
        expected = CODES[code_id]['sets']
        if len(sets_list) != expected:
            flash(f'{code_id}는 {expected}세트 필요, {len(sets_list)}세트 입력됨', 'warning')
        result = save_predictions(round_number, code_id, sets_list)
        if result:
            flash(f'{round_number}회차 {CODES[code_id]["name"]} {len(sets_list)}세트 저장 ✓', 'success')
        else:
            flash(f'{round_number}회차가 존재하지 않습니다. 먼저 당첨 번호를 등록하세요.', 'error')
    except (ValueError, KeyError) as e:
        flash(f'입력 오류: {e}', 'error')
    return redirect(url_for('input_page'))

@app.route('/history')
def history():
    rounds = get_all_rounds()
    return render_template('history.html', rounds=rounds, codes=CODES)

@app.route('/round/<int:round_number>')
def round_detail(round_number):
    analysis = get_round_detail_analysis(round_number)
    if not analysis:
        flash(f'{round_number}회차 데이터가 없습니다.', 'error')
        return redirect(url_for('history'))
    return render_template('round_detail.html',
                           round_number=round_number, analysis=analysis, codes=CODES)

@app.route('/round/<int:round_number>/delete', methods=['POST'])
def round_delete(round_number):
    delete_round(round_number)
    flash(f'{round_number}회차가 삭제되었습니다.', 'success')
    return redirect(url_for('history'))

@app.route('/api/dashboard')
def api_dashboard():
    return jsonify(get_dashboard_data())

@app.route('/api/round/<int:round_number>/status')
def api_round_status(round_number):
    data = get_round_data(round_number)
    if not data:
        return jsonify({'exists': False})
    status = {}
    for code_id in CODES:
        if code_id in data['predictions']:
            status[code_id] = {'entered': True, 'sets': len(data['predictions'][code_id])}
        else:
            status[code_id] = {'entered': False, 'sets': 0}
    return jsonify({'exists': True, 'round_number': round_number, 'actual': data['actual'], 'codes': status})

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=os.environ.get('FLASK_ENV') == 'development')
