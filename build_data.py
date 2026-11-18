#!/usr/bin/env python3
"""把 7 个周期的 XAU Combo 指标原始结果 + 1m OHLCV 变成 data.json。
用法: python3 build_data.py [raw_dir]   (默认 ./raw)
raw_dir 里需要: 4H.txt 1H.txt 30m.txt 15m.txt 5m.txt 3m.txt 1m.txt ohlcv_1m.txt
（每个文件就是 run-pine-indicator / get-ohlcv 的原始返回，write_to_file 产生的文件可以直接复制进来）
"""
import json, sys, time, urllib.request, pathlib, datetime
D = pathlib.Path(__file__).resolve().parent
RAW = pathlib.Path(sys.argv[1]) if len(sys.argv) > 1 else D / 'raw'
TFS = ['4H', '1H', '30m', '15m', '5m', '3m', '1m']
TZ = datetime.timezone(datetime.timedelta(hours=8))

def load(p):
    best = None
    for line in open(p, encoding='utf-8'):
        line = line.strip()
        if line.startswith('{'):
            try: best = json.loads(line)
            except Exception: pass
    if not best or not best.get('success', True):
        sys.exit(f'build_data: 无法解析 {p}')
    return best

def r1(x): return round(float(x), 1)

T = {}
for tf in TFS:
    d = load(RAW / f'{tf}.txt')
    p = d['values'][-1]['plots']; v = lambda i: p.get(f'plot_{i}')
    zl, rf = int(v(1) or 0), int(v(5) or 0)
    fh1, fh2, fl1, fl2 = v(11), v(12), v(13), v(14)
    hi = 'HH' if fh1 and fh2 and fh1 > fh2 else 'LH'
    lo = 'HL' if fl1 and fl2 and fl1 > fl2 else 'LL'
    T[tf] = dict(t=d['values'][-1]['t'], close=v(0), zl=zl, zlema=v(2), vol=v(3), filt=v(4), rf=rf,
                 rfsig=int(v(6) or 0), rfbars=int(v(7) or 0), mom=v(8), msl=int(v(9) or 0), msbars=int(v(10) or 0),
                 fh1=fh1, fh2=fh2, fl1=fl1, fl2=fl2, hi=hi, lo=lo, struct=f'{hi}/{lo}',
                 dir=zl if zl == rf else 0)
price = T['1m']['close']
for tf in TFS:
    t = T[tf]; band = t['vol']
    t['pull'] = abs(price - t['zlema']) <= band or abs(price - t['filt']) <= band  # 回到 zlema / filt 附近

# ---------- 总指挥规则 ----------
big = T['4H']['dir'] if T['4H']['dir'] != 0 and T['4H']['dir'] == T['1H']['dir'] else 0
DN = {1: '多', -1: '空', 0: '观望'}
def struct_ok(t, d): return (d == 1 and t['lo'] == 'HL') or (d == -1 and t['hi'] == 'LH')

status = {}
for tf in ['4H', '1H']:
    status[tf] = 'exec' if big != 0 else ('pause' if T[tf]['dir'] != 0 else 'filter')
for tf in ['30m', '15m']:
    t = T[tf]
    if big == 0: status[tf] = 'pause' if t['dir'] != 0 else 'filter'
    else:
        a, b = t['dir'] == big, struct_ok(t, big)
        status[tf] = 'exec' if a and b else 'pause' if (a or b) and t['dir'] != -big else 'filter'
for tf in ['5m', '3m']:
    t = T[tf]
    if big == 0: status[tf] = 'pause' if t['dir'] != 0 and t['msl'] == t['dir'] else 'filter'
    else:
        sc = [t['dir'] == big, t['pull'], t['msl'] == big]
        status[tf] = 'exec' if all(sc) else 'pause' if any(sc) and t['dir'] != -big else 'filter'

lower = ['30m', '15m', '5m', '3m']
if big == 0: strength = '弱'
elif status['30m'] == 'exec' and status['15m'] == 'exec' and 'exec' in (status['5m'], status['3m']): strength = '强'
elif sum(T[x]['dir'] == big for x in lower) >= 2: strength = '中'
else: strength = '弱'
npull = sum(T[x]['pull'] for x in ['5m', '3m', '1m'])
quality = '好' if npull >= 2 else '中' if npull == 1 else '差'
if big == 0 and quality == '好': quality = '中'
m1 = T['1m']
entry = big != 0 and strength == '强' and quality in ('好', '中') and m1['msl'] == big and m1['dir'] != -big
status['1m'] = 'exec' if entry else ('pause' if big != 0 else 'filter')
status['exec'] = 'exec' if entry else ('pause' if big != 0 and strength != '弱' else 'filter')

# ---------- 关键价位 ----------
cand = [(T['4H']['filt'], '4H RF filt'), (T['4H']['zlema'], '4H zlema'), (T['1H']['filt'], '1H RF filt'), (T['1H']['zlema'], '1H zlema')]
for tf in ['4H', '1H', '30m', '15m']:
    t = T[tf]
    for a, b, kind in ((t['fh1'], t['fh2'], '高'), (t['fl1'], t['fl2'], '低')):
        if a and b and abs(a - b) <= 1.5 * t['vol']:   # 两个分形挨得近 = 一个区间，标上下沿
            cand += [(max(a, b), f'{tf} {kind}点区上沿'), (min(a, b), f'{tf} {kind}点区下沿')]
        else:
            cand += [(x, f'{tf} 前{kind}{n}') for x, n in ((a, ''), (b, '2')) if x]
cand += [(T['30m']['filt'], '30m RF filt'), (T['15m']['filt'], '15m RF filt'), (T['5m']['zlema'], '5m zlema')]
levels = []
for p, n in cand:
    if p is None: continue
    if any(abs(p - l['p']) < 0.8 for l in levels): continue
    levels.append(dict(p=r1(p), name=n, type='res' if p > price else 'sup'))
inv_names = {'1H RF filt'} | ({'4H RF filt'} if big == 0 else set())
for l in levels:
    if l['name'] in inv_names: l['type'] = 'inv'; l['name'] += ' 失效线'
levels.sort(key=lambda l: -l['p'])
f1, f4 = r1(T['1H']['filt']), r1(T['4H']['filt'])
fr_lows = [x for tf in ['1H', '30m', '15m'] for x in (T[tf]['fl1'], T[tf]['fl2']) if x and x < price]
fr_highs = [x for tf in ['1H', '30m', '4H'] for x in (T[tf]['fh1'], T[tf]['fh2']) if x and x > price]
reg_lo = r1(max(fr_lows)) if fr_lows else r1(min(l['p'] for l in levels))
reg_hi = r1(min(fr_highs)) if fr_highs else r1(max(l['p'] for l in levels))
trend = {1: '偏多', -1: '偏空', 0: '震荡'}[big]

def targets(ref, d):
    ps = sorted({l['p'] for l in levels if (l['p'] < ref - 3 if d < 0 else l['p'] > ref + 3)}, reverse=d < 0)
    out = []
    for p in ps:
        if not out or abs(p - out[-1]) >= 3: out.append(p)
        if len(out) == 2: break
    return out or [ref]
def tr(xs): return '–'.join(f'{x:.1f}' for x in xs)

res = [l for l in levels if l['p'] > price][-3:][::-1]; sup = [l for l in levels if l['p'] < price][:3]
kp = '阻力 ' + '、'.join(f"{l['p']:.1f}（{l['name']}）" for l in res) + '；支撑 ' + '、'.join(f"{l['p']:.1f}（{l['name']}）" for l in sup)
kp += f'；区间 {reg_lo:.1f}–{reg_hi:.1f}'
if big == 0:
    s_t, l_t = targets(f1, -1), targets(f4, 1)
    advice = (f"观望，不进场。4H {DN[T['4H']['dir']]}（ZL {DN[T['4H']['zl']]}、RF {DN[T['4H']['rf']]}，filt {f4:.1f}），"
              f"1H {DN[T['1H']['dir']]}（ZL {DN[T['1H']['zl']]}、RF {DN[T['1H']['rf']]}，filt {f1:.1f}），两者不同向。"
              f"等其一：① 1H 收盘跌破 {f1:.1f} 与 4H 同向转空，再等 5m/3m 反抽 zlema/filt 且动能转空做空，目标 {tr(s_t)}；"
              f"② 4H 收盘站上 {f4:.1f} 且 ZL 转多与 1H 同向，再等回调做多，目标 {tr(l_t)}。目标仅供参考，不保证达到。")
    inval = f"观望结论在 1H 收盘跌破 {f1:.1f}（转空共振）或 4H 收盘站上 {f4:.1f}（转多共振）时失效，届时重新判断。"
else:
    w = '做多' if big == 1 else '做空'; tg = targets(price, big)
    zl1 = r1(T['5m']['zlema'])
    advice = (f"{'可以去1m寻找入场，' if entry else '等待，暂不入场，'}方向只{w}。"
              f"等价格回到 5m zlema {zl1:.1f} / 1H filt {f1:.1f} 附近、1m 动能同向加速再入场，目标 {tr(tg)}。目标仅供参考，不保证达到。")
    inval = f"1H 收盘{'跌破' if big == 1 else '站上'} {f1:.1f}（1H RF filt）{w}思路失效；4H 与 1H 不再同向也失效。"
risk = ("指标基于 OANDA:XAUUSD，最后一根 K 线未收盘，读数会变；页面实时 K 线用 Binance PAXG/USDT 加价差近似，可能差几美元。"
        "本页面只是技术指标的整理，不构成交易建议，请自己控制仓位和止损。")

def desc(tf):
    t = T[tf]
    if tf in ('4H', '1H'): return f"ZL{DN[t['zl']]}·RF{DN[t['rf']]}"
    if tf in ('30m', '15m'): return f"{DN[t['dir']]}·结构 {t['struct']}"
    return f"{'贴 zlema/filt' if t['pull'] else '离 zlema'}·动能{'↑' if t['msl'] == 1 else '↓'}"

# ---------- basis ----------
# 用和 OANDA 1m 同一根 K 线时间的 PAXG 1m 收盘价，避免时间差
paxg, src = None, ''
for host in ['https://api.binance.com', 'https://data-api.binance.vision']:
    try:
        u = f"{host}/api/v3/klines?symbol=PAXGUSDT&interval=1m&startTime={m1['t'] * 1000}&limit=1"
        with urllib.request.urlopen(u, timeout=8) as r:
            k = json.load(r)
        if k: paxg = float(k[0][4]); src = host.split('//')[1] + ' 1m@' + datetime.datetime.fromtimestamp(m1['t'], TZ).strftime('%H:%M'); break
    except Exception: pass
old = {}
try: old = json.loads((D / 'data.json').read_text())
except Exception: pass
basis = round(price - paxg, 2) if paxg else old.get('basis', 0)

oh = load(RAW / 'ohlcv_1m.txt')['bars']
if isinstance(oh, dict):
    bars = [[oh['t'][i], oh['o'][i], oh['h'][i], oh['l'][i], oh['c'][i]] for i in range(len(oh['t']))]
else:
    bars = [[b['t'], b['o'], b['h'], b['l'], b['c']] for b in oh]

now = int(time.time())
data = dict(
    version=1, symbol='OANDA:XAUUSD',
    updated=datetime.datetime.fromtimestamp(now, TZ).strftime('%Y-%m-%d %H:%M'), updated_ts=now,
    bar_time=datetime.datetime.fromtimestamp(m1['t'], TZ).strftime('%H:%M'),
    price=r1(price), basis=basis, basis_src=f'PAXGUSDT {paxg} @ {src}' if paxg else '沿用上次 basis',
    regime=dict(low=reg_lo, high=reg_hi, trend=trend),
    verdict=dict(dir=DN[big], strength=strength, quality=quality, entry='是' if entry else '否'),
    advice={'操作建议': advice, '关键价位': kp, '失效条件': inval, '风险提示': risk},
    commander=dict(tf='1m', status=status['1m'],
                   desc='执行信号!' if entry else f"总指挥 · {'等回调信号' if big else '等 4H/1H 同向'}"),
    exec=dict(name='执行', status=status['exec'], desc='总指挥放行' if entry else '未放行'),
    analysts=[dict(tf=tf, status=status[tf], desc=desc(tf)) for tf in TFS[:6]],
    tfInfo={tf: dict(trend=DN[T[tf]['zl']], rf=DN[T[tf]['rf']], zlema=r1(T[tf]['zlema']), filt=r1(T[tf]['filt']),
                     ms=f"{T[tf]['mom']:+.1f}", zz=T[tf]['struct'], close=r1(T[tf]['close'])) for tf in TFS},
    levels=levels,
    fallback=dict(tf='1m', note='OANDA:XAUUSD 1m（分析时）', bars=bars[-120:]),
)
(D / 'data.json').write_text(json.dumps(data, ensure_ascii=False, indent=1))
print(f"data.json 已写入 {data['updated']} 方向={data['verdict']['dir']} 共振={strength} 回调={quality} 1m={data['verdict']['entry']} basis={basis}")
