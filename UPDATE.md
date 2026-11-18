# XAUUSD 总指挥 · 15 分钟更新流程

页面: https://xmond1234.github.io/xauusd-/ （仓库 Xmond1234/xauusd-，分支 main，目录 /home/box/xauusd-gh）
规则: 只读 TradingView，不创建/修改任何 alert、设置、布局。不要打印令牌。

## 每次运行（按顺序）

1. 用 `user-Tradingview-xai` 的 `mcp-tv-run-pine-indicator` 跑 7 次（同时最多 2 个），每次都带 `"write_to_file": true`：
   固定参数 `code: "$file:/workspace/xau_combo.pine"`, `symbol: "OANDA:XAUUSD"`, `calc_bars_count: 1500`, `return_bars: 1`

   | 存为 raw/ | timeframe | in_0 | in_1 | in_2 | in_3 | in_4 | in_5 |
   |---|---|---|---|---|---|---|---|
   | 4H.txt  | 4h  | 9  | 0.3 | 50 | 1.1 | 12 | 6  |
   | 1H.txt  | 1h  | 11 | 0.4 | 50 | 0.9 | 29 | 6  |
   | 30m.txt | 30m | 9  | 0.1 | 50 | 1.0 | 15 | 4  |
   | 15m.txt | 15m | 15 | 0.2 | 50 | 0.9 | 18 | 8  |
   | 5m.txt  | 5m  | 18 | 0.4 | 50 | 1.0 | 12 | 10 |
   | 3m.txt  | 3m  | 16 | 0.4 | 50 | 1.0 | 16 | 10 |
   | 1m.txt  | 1m  | 20 | 0.5 | 50 | 1.0 | 15 | 18 |

2. `mcp-tv-get-ohlcv`：`{"symbol":"OANDA:XAUUSD","interval":"1m","count":120,"format":"columns"}`，`write_to_file: true`，存为 raw/ohlcv_1m.txt。
3. 把每个结果文件复制过去：`cp <返回的文件路径> /home/box/xauusd-gh/raw/<名字>.txt`（文件原样复制即可，脚本会自己找出 JSON）。
4. 运行：
   ```
   cd /home/box/xauusd-gh && python3 build_data.py && ./push.sh
   ```
   build_data.py 会自己取同一分钟的 Binance PAXGUSDT 1m 收盘价算 basis，写 data.json；push.sh 提交并推送（无变化时也返回 0，失败返回非 0）。
5. 把 build_data.py 打印的一行（方向/共振/回调/1m）作为本次结果；除非 `1m=是` 或用户要求，否则不必打扰用户。

任何一步失败：不要推送半成品，报告是哪一步失败。周末（OANDA 休市）可以跳过。

## build_data.py 的判断规则（总指挥规则）

指标列: plot_0 close, 1 zl_trend, 2 zlema, 3 zl_vol, 4 rf_filt, 5 rf_dir, 6 rf_last_sig, 7 rf_bars_since, 8 ms_mom, 9 ms_last, 10 ms_bars_since, 11/12 前两个分形高点, 13/14 前两个分形低点, 15–18 zz0–zz3, 19 zz type, 20 zz bars, 21/22 ZL 多/空入场距今。取 `values[-1]`（最新一根，可能未收盘）。

- 每个周期方向 dir = zl_trend 与 rf_dir 相同时取该值，否则 0。结构 = 分形高点 HH/LH + 低点 HL/LL。
- **大方向**: 4H dir = 1H dir ≠ 0 时为 多/空，否则 观望（趋势 震荡），1m 必为 否。
- 回调 pull: |1m 价 − 该周期 zlema| 或 |价 − filt| ≤ 该周期 zl_vol。
- 状态（exec 执行 / pause 暂停 / filter 过滤）:
  - 4H/1H: 有大方向=执行；没有时自己有方向=暂停，否则过滤。
  - 30m/15m: 方向同大方向且结构支持（多要 HL、空要 LH）=执行；满足其一且不逆向=暂停；否则过滤。（无大方向时：有方向=暂停）
  - 5m/3m: 方向同向 + 回调 + Momentum ms_last 同向 全满足=执行；部分满足且不逆向=暂停；否则过滤。（无大方向时：方向与动能一致=暂停）
- 共振强度: 强 = 30m、15m 都执行且 5m/3m 至少一个执行；中 = 4 个低周期中 ≥2 个同向；否则弱（无大方向=弱）。
- 回调质量: 5m/3m/1m 中 ≥2 个回调=好，1 个=中，0=差（无大方向最多 中）。
- 是否提醒1m进场 = 是：有大方向 + 共振强 + 回调≥中 + 1m ms_last 同向 + 1m 不逆向。1m 总指挥和执行节点只有此时=执行。
- 关键价位: 4H/1H zlema 与 filt、4H/1H/30m/15m 分形高低点（两点挨近时标 上沿/下沿）、30m/15m filt、5m zlema；去重 0.8；价在上=res，下=sup；1H filt（无大方向时还有 4H filt）=inv 失效线。
- 区间: 当前价下方最近的 1H/30m/15m 分形低点 ~ 上方最近的 1H/30m/4H 分形高点。

## data.json 结构
```
data.json 结构（由 build_data.py 生成，页面每 60 秒读取一次 ./data.json?t=时间戳）
{
  "version": 1, "symbol": "OANDA:XAUUSD",
  "updated": "YYYY-MM-DD HH:MM",        // 分析时间 UTC+8
  "updated_ts": 1795010322,              // 分析时间 unix 秒；超过 30 分钟页面显示过期警告
  "bar_time": "HH:MM",                   // 1m 指标所用 K 线时间 UTC+8
  "price": 3787.8,                       // OANDA 1m 收盘价
  "basis": 5.57,                         // OANDA 收盘 − 同一分钟 PAXGUSDT 收盘；实时 K 线 + basis
  "basis_src": "说明文字",
  "regime": {"low": 3759.0, "high": 3798.0, "trend": "震荡|偏多|偏空"},
  "verdict": {"dir": "多|空|观望", "strength": "强|中|弱", "quality": "好|中|差", "entry": "是|否"},
  "advice": {"操作建议": "", "关键价位": "", "失效条件": "", "风险提示": ""},
  "commander": {"tf": "1m", "status": "filter|pause|exec", "desc": ""},   // 1m 总指挥
  "exec": {"name": "执行", "status": "filter|pause|exec", "desc": ""},    // 执行节点
  "analysts": [{"tf": "4H|1H|30m|15m|5m|3m", "status": "filter|pause|exec", "desc": ""}],  // 6 个，按此顺序
  "tfInfo": {"4H": {"trend": "多|空", "rf": "多|空", "zlema": 0, "filt": 0, "ms": "+1.0", "zz": "HH/HL", "close": 0}, ...},
  "levels": [{"p": 3798.4, "name": "4H RF filt 失效线", "type": "res|sup|inv"}],
  "fallback": {"tf": "1m", "note": "", "bars": [[unix秒, o, h, l, c], ...]}   // Binance 不可用时显示（OANDA 价，不加 basis）
}
status: filter=过滤(灰) pause=暂停(橙) exec=执行(绿)
```

## 首次设置（只做一次）
令牌需要仓库权限 Contents: Read and write（推送），Pages: Read and write + Administration: Read and write（用 API 开 Pages）。
没有后两项时，让用户在仓库 Settings → Pages → Branch 选 main / (root) → Save。
API 开 Pages（已存在会返回 409，也算成功）：
`curl -s -o /dev/null -w '%{http_code}' -X POST -H "Authorization: Bearer $GITHUB_XAUUSD_TOKEN" https://api.github.com/repos/Xmond1234/xauusd-/pages -d '{"source":{"branch":"main","path":"/"}}'`
