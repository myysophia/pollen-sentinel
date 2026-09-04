# PollenSentinel · 花粉哨兵

> 比花粉早知道一步。面向过敏性鼻炎人群的**花粉监测 → 预测 → 症状管理**开源工具，零第三方 Python 依赖，GitHub Actions 免费运行。

- 全国 **53 个官方监测城市**每日自动采集花粉过敏指数（6 级），快照永久入库
- 基于降水冲刷 / 降温 / 季节物候的**可解释 L1 规则预测**（未来 7 天，标注官方预报与置信度）
- 个人鼻炎管理日报：风险卡、35 天趋势、日历热力、影响因素、本季统计、**症状-花粉叠加日记**、防护清单、每日寄语
- 全国风险看板（GitHub Pages 静态托管）
- 症状日记支持浏览器本地记录 + 仓库归档双轨，跨设备可查

## 数据源

| 数据 | 来源 | 覆盖 / 频率 | 授权 |
|---|---|---|---|
| 花粉等级（主源） | 中国天气网 · 北京同仁医院「花粉过敏指数」 | 53 监测城市，每日下午发布实况+预报，历史可回溯至 2022-08 | 公开页面数据，仅个人健康用途，请求保持克制 |
| 天气预报 / 历史气象 | [Open-Meteo](https://open-meteo.com) Forecast + ERA5 Archive | 全球网格，7 天预报 / 历史再分析 | CC BY 4.0，无需 key |
| 扩展备选（未启用） | 和风天气生活指数、pollencount.org | 用于后续覆盖非监测城市 | 需各自 key / 注明来源 |

> 说明：Open-Meteo 的逐物种花粉（艾蒿/豚草等）仅覆盖欧洲，中国区域为空，故不采用；官方接口为内部 JSON 接口、无 SLA，采集器内置重试与失败记录，必要时需更新适配。

## 目录结构

```
pollen-sentinel/
├── config/cities.json        # 53 监测城市（代码/拼音/省份/经纬度）
├── collectors/               # 采集层（标准库实现）
│   ├── pollen_cma.py         #   中国天气网花粉：抓取、规范化、类型判定
│   ├── weather_om.py         #   Open-Meteo 预报/归档 + WMO 天气码
│   └── collect.py            #   批量编排：原始快照 + 规范化 CSV
├── predictor/rules.py        # L1 可解释规则预测
├── reporter/                 # 个人 HTML 日报（ECharts CDN，单文件）
├── scripts/
│   ├── run_daily.sh          # 每日流水线：采集→日报→看板数据
│   └── export_web.py         # 生成 web/data.json
├── web/                      # GitHub Pages 站点
│   ├── index.html            #   全国风险看板
│   └── reports/              #   个人日报（latest + 按日归档）
├── data/
│   ├── raw/<date>/<city>.json  # 每日原始快照（含当时预报，供回测）
│   ├── daily/                # 规范化 CSV（pollen / weather）
│   └── personal/diary.json   # 本人症状日记归档（公开，自愿）
├── tests/                    # 预测器单元测试
└── .github/workflows/        # ci / daily-collect / deploy-pages
```

## 本地运行

需要 Python 3.10+（无需 pip install）：

```bash
# 1) 采集（默认全部 53 城；指定城市更快）
python3 -m collectors.collect --cities xian,xianyang --days 40

# 2) 生成个人日报
python3 -m reporter.build_report --cities xian,xianyang --out web/reports/latest.html

# 3) 生成全国看板数据
python3 scripts/export_web.py

# 或一键完成：
bash scripts/run_daily.sh

# 一次性回填 2022 年以来全部历史（约 53 城 × 5 年，耗时较长）
python3 -m collectors.collect --backfill --sleep 0.8

# 测试
python3 -m unittest discover -s tests
```

## 预测方法（路线图）

- **L1 规则预测（当前）**：以最新实测为锚点，官方已发布预报优先；其余日期按气象逐日推演——≥10mm 降水降 2 级、小雨降 1 级、昨日大雨滞后再降、强降温（≥6℃）抑制、爬升/高峰期连续干燥有风升 1 级，非花粉季封顶为很低。每个结论都给出中文理由与置信度（1-2 天中、3 天以上低）。
- **L2 机器学习（规划）**：快照积累后，以过去 7 天等级、Open-Meteo 预报、积温、年序日、城市为特征，做有序等级分类（XGBoost / 有序回归），walk-forward 回测，主指标为「高及以上」召回率与 ±1 级命中率。不做伪精确的粒数回归。
- **L3 个性化（规划）**：基于 `data/personal/diary.json` 预测个人次日症状分与用药效果。

## GitHub Actions 与 Pages

- `daily-collect.yml`：每天 **07:00 / 17:30（北京时间）** 运行流水线并自动提交数据（也支持手动 workflow_dispatch，可填城市）
- `deploy-pages.yml`：`web/` 变更后自动部署 Pages
- `ci.yml`：push/PR 时编译检查 + 单元测试

首次启用 Pages：仓库 **Settings → Pages → Source 选 "GitHub Actions"**。部署后访问：
- 全国看板 `https://<owner>.github.io/pollen-sentinel/`
- 个人日报 `https://<owner>.github.io/pollen-sentinel/reports/latest.html`

## 自定义

- 换关注城市：改 `daily-collect.yml` 的 `REPORT_CITIES`（城市 en 名见 `config/cities.json`）
- 推送时间：改 workflow cron（UTC，北京时间 = UTC+8）
- 寄语库：`reporter/build_report.py` 的 `CHEERS`

## 数据与隐私

环境花粉数据全部公开、随仓库保存；个人症状日记仅在你主动写入 `data/personal/diary.json` 后才公开，浏览器 localStorage 中的记录不会自动上传，导出与提交由你手动完成，**请勿写入身份信息**。

## 免责声明

本项目为个人健康管理与技术研究工具，花粉数据版权归原来源所有；报告内容不替代医生面诊与处方，具体诊断与用药请遵医嘱。

## License

[MIT](LICENSE)
