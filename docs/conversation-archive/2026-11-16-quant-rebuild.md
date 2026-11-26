# 会话归档：量化数据分析与预警平台重新立项

## 2026-11-16

- **[决策·已定]** 重新做产品，不在 `lianghua` 与 `everything` 上继续迭代。理由：用户明确表态；代价：两个既有子项目的定位与既有 ADR 需重新界定是否仍有效（待确认）。
- **[变更]** 原需求「在 TradeTrace 仓库内，`lianghua` 只做只读行情、`everything` 做交易记录与复盘，两者解耦演进」→ 新需求「以新产品形态重做量化数据分析与预警平台，含 Web 端与 Android 端」。原因：用户原话「我想重新做这个产品，不再在lianghua和everything上做迭代」。
- **[术语]** 产品定位 = 股票市场量化数据分析 + 预警提醒，**不做交易**（不接券商下单接口）。
- **[约束]** 端形态固定为 Web 端 + Android 端两端。
- **[约束]** 本机已安装的 zh 系列 skills 为：`zh-ask-matt`、`zh-grill-with-docs`、`zh-grilling`、`zh-domain-modeling`、`zh-codebase-design`、`zh-to-spec`、`zh-to-tickets`、`zh-implement`、`zh-implement-spec`、`zh-tdd`、`zh-code-review`、`zh-setup-matt-pocock-skills`；**未安装** `zh-wayfinder`、`zh-prototype`、`zh-handoff`、`zh-triage`、`zh-retro` 等。greenfield 只能走 grill → spec → tickets → implement 路径。
- **[约束]** 仓库 `f:\Project\TradeTrace` 为 GitHub 远端 `LiMuwenan/TradeTrace`；尚无 `GLOSSARY.md`、`docs/adr/`、`.scratch/`、`CLAUDE.md`。
- **[决策·已定]** 新产品代码落在**本仓库 `f:\Project\TradeTrace` 下的新建目录**，`lianghua` 与 `everything` 保留作为参考实现。备选：独立新仓库、本仓库新分支。代价：同仓多项目并存，需在文档层面划清边界。（目录名待定）
- **[开放问题]** 是否复用 `lianghua` 已有的数据摄取与行情服务能力（Parquet 存储、csv_import、index_ingest、scanner、scheduler 等），还是完全重写 → 用户选择「先访谈再定」，作为 grilling 首个议题（未定）。
- **[开放问题]** 上一轮给出的能力地图与分期（P0 自选+分级预警+预警事后验证；P1 条件选股/观察组合/回测；P2 多因子/分钟线）为 agent 建议，用户尚未确认，不作为已定需求。
- **[风险]** `lianghua`、`everything` 与新产品同处一个仓库，若不正视边界，后续容易按旧 ADR（服务端只做只读行情、交易截图端上 OCR、家庭局域网无鉴权）误判新产品约束。触发条件：开始写代码或拆 ticket 时。
- **[待办]** 待用户确认仓库边界后，执行 `zh-setup-matt-pocock-skills` → `zh-grill-with-docs` → `zh-to-spec` → `zh-to-tickets` → `zh-implement`。

## 2026-11-16（setup 阶段）

- **[决策·已定]** Issue tracker 用 **local markdown**：`.scratch/<feature>/`，一个 ticket 一个文件，纳入 git。放弃 GitHub Issues，原因：本机未安装 `gh` CLI，且为单人项目。代价：issue 不同步到 GitHub 网页端。
- **[放弃]** GitHub Issues / Jira / Linear 等外部 tracker。重启需注意：若以后要多人协作，需先装 `gh` 并改 `docs/agents/issue-tracker.md`。
- **[约束]** `triage` skill 未安装，因此**不配置 triage labels**，`AGENTS.md` 中也不写 Triage labels 段。
- **[决策·已定]** Domain docs 走 **single-context**：根目录 `GLOSSARY.md` + `docs/adr/`。理由：仓库无 monorepo 信号（无根 `package.json`/`pnpm-workspace.yaml`）。代价：三个子项目共用一份词汇表，同词异义必须在词汇表里标作用域。
- **[契约]** setup 写入：`AGENTS.md` 新增 `## Agent skills` 段；新增 `docs/agents/issue-tracker.md`、`docs/agents/domain.md`。后续 `zh-to-spec`、`zh-to-tickets`、`zh-implement` 读这些文件。
- **[待办]** 下一步执行 `zh-grill-with-docs`，首个议题仍是「lianghua 数据层复用还是重写」。

## 2026-11-16（grilling 第一轮）

- **[决策·已定]** 复制 `lianghua` 的 `datasources/baostock.py`、`parquet_store.py`、`index_store.py` 到新项目目录，接受双份维护。放弃「直接 import」与「完全重写」；抽成共享包留待后续。理由：`parquet_store` 的 24 列 schema（含复权因子与估值）是资产；根 `AGENTS.md` 禁止跨项目 import。
- **[决策·已定]** 预警只做**日频**（收盘后计算 + 次日盘前提醒），不做盘中实时。
- **[决策·已定]** **不并入** `everything` 的交易记录、做T、收益统计；新产品只消费行情数据，不含持仓概念。
- **[决策·已定]** **单用户**，不做登录、不做多租户。
- **[决策·已定]** 部署在**家庭局域网**，放弃公网部署与 App 服务端推送。备选（云服务器 + WebSocket 推送、第三方推送服务）已放弃。
- **[风险]** 局域网部署与「预警随时触达」直接冲突：手机离开家庭 Wi-Fi 后收不到任何服务端通知。缓解方向待定（邮件出站兜底 / 弱化为打开 App 才看到 / 隧道回公网）。
- **[约束]** 已核实 `lianghua` 数据现状：baostock 单源，仅日 K、复权因子、指数日线；Parquet 按股票存 `{code}.parquet`；`scanner.py` 是策略 manifest 扫描器，不是预警引擎。
- **[开放问题]** 新目录名；后端/Web/Android 技术栈；「一次触发」的判定与去噪策略；P0 范围（未定）。

## 2026-11-16（grilling 第二轮）

- **[决策·已定]** 新目录名 `quant/`（与 `lianghua/`、`everything/` 并列）。
- **[决策·已定]** 技术栈：后端 Python/FastAPI（由复制来的数据层决定）+ Web 端 Vue 3（参照 `lianghua/web`）+ Android 端 Expo/React Native（参照 `everything`）。接受两套前端技术栈。
- **[决策·已定]** 预警采用**边沿触发**：每条「标的 + 规则」维护触发态，只在「否→是」时产生一条预警，回落到「否」后才可能再次触发；叠加每日推送上限与日报兜底。放弃电平触发（每天一条，会淹没用户）与纯日报（丢失及时性）。
- **[决策·已定]** P0 范围：自选列表 → 个股详情（K 线 + 指标）→ 日频规则（突破/超跌/放量/均线）→ 边沿触发记录 → App 列表 + 推送 + 邮件 → 每日摘要。条件选股、回测、多因子推迟到 P1。
- **[决策·已定]** 数据源继续只用 baostock，P0 不引入第二个源。
- **[澄清]** 「局域网 + 能出网」不等于不能推送：推送要求手机连到一个**公网可达**的长连接端点，但端点可以是第三方的（ntfy / 飞书机器人 / 厂商推送），不必自建公网服务。只有「自建 WebSocket 推送」才需要公网 VPS 或隧道。
- **[开放问题]** Q6' 推送通道最终选择（第三方 webhook / 厂商 SDK / 公网 VPS 自建 / 仅邮件）待定。
- **[契约]** 新增根目录 `GLOSSARY.md`，首批词条：自选、规则、触发、预警、日报、持仓（显式排除）。

## 2026-11-16（grilling 第三轮）

- **[决策·已定]** 推送通道选 **ntfy 优先**：家里服务器出网 POST 到 ntfy 主题，Android 端用 ntfy 客户端收通知，邮件作为兜底。放弃厂商推送 SDK 与公网 VPS 自建推送。
- **[变更]** 推翻第一轮「复制 `datasources/baostock.py`」的结论。新结论：**只复用 parquet 存储层**（`parquet_store.py`、`index_store.py`），**baostock 取数逻辑重写**。原因：用户明确要求取数逻辑重新实现。
- **[开放问题]** 重写取数逻辑的目标差异（增量/可重跑/字段缺口/代码质量）待澄清。
- **[开放问题]** `quant/` 是否使用独立数据目录、历史数据是否需要重新灌入（与根 `AGENTS.md`「禁止直接读写对方目录」相关）待定。

## 2026-11-16（grilling 第四轮）

- **[决策·已定]** 重写取数逻辑的动因是**现有代码质量差、难维护、错误处理不清晰**（而非字段缺口或增量能力）。因此新实现的验收重点是可读性、失败可见、可重跑，不是新增数据字段。
- **[决策·已定]** `quant/` 使用**独立且可配置**的数据目录（路径写在配置里，不硬编码），历史数据重新灌入；不复用 `lianghua` 的 parquet 数据文件，不改 `AGENTS.md` 边界规则。
- **[开放问题]** Android App 的 P0 页面范围未定（目前只确定「预警列表 + 推送」，自选、个股详情、日报是否进 App 未定）。
- **[开放问题]** App 离开家庭局域网后无法访问服务端，预警通知体是否携带足够信息以支撑离线判断，未定。

## 2026-11-16（grilling 收束）

- **[决策·已定]** Android App P0 只做两页：预警列表（已读/未读）+ 预警详情（触发快照）；个股详情跳转浏览器打开 Web。放弃「三页含自选行情列表」与「完整复刻 Web」。
- **[决策·已定]** 通知体自带数据：标的、触发规则、触发价、阈值、数据日期，保证不打开 App 也能判断。
- **[契约]** 新增 ADR：`docs/adr/0001-quant-project-boundary.md`（目录边界与数据层复用范围）、`docs/adr/0002-daily-edge-trigger-alert-model.md`（日频边沿触发）、`docs/adr/0003-lan-deployment-and-ntfy-push.md`（局域网 + ntfy + 双端分工）。
- **[待办]** frontier 已清空；下一步 `zh-to-spec`，把本会话结论收束为 spec，再 `zh-to-tickets` 拆 ticket。

## 2026-11-16（spec 阶段）

- **[决策·已定]** 测试 seam 定为两个：规则求值器（纯函数 + fixture 行情）+ HTTP API（FastAPI TestClient）。数据源适配器不作 seam，测试时用假数据替换。
- **[契约]** spec 落盘 `docs/specs/2026-11-16-quant-p0.md`，状态 `ready-for-agent`，含 22 条 user stories、Implementation Decisions、Testing Decisions、Out of Scope。
- **[契约]** spec 中的补充约定：交易日以行情实际存在的日期为准；增量游标为「最后已入库交易日」；预警唯一键为「标的 + 规则 + 交易日」；每日推送上限默认 10 条；API 统一 `/api/v1` + camelCase。
- **[待办]** 下一步 `zh-to-tickets`，把 spec 拆成带 blocking edges 的 ticket 写入 `.scratch/quant-p0/`。

## 2026-11-16（量比定义与取数逻辑）

- **[决策·已定]** 放量/缩量统一用「量比」：当日成交量 ÷ 前 N 日均量，均值**不含当日**（避免当日放量抬高基准），N 默认 5，放量阈值默认 1.5、缩量阈值默认 0.6，按规则可配。
- **[需求变更]** 用户持有历史数据资产：按交易日横截面的日 K 文件 + 同结构的日复权因子文件。历史导入因此改为「横截面 → 按标的时间序列」的列转置，不再依赖 baostock 回灌。
- **[决策·已定]** 行情存储粒度从「每标的 1 文件」改为 **「标的 + 年份」分区**（每标的每年 1 文件）；每日增量只重写当年文件，读取近 N 日只需 1–2 个文件。新增 `docs/adr/0004-partitioned-market-data-storage.md`。
- **[决策·已定]** 每日增量只拉自选标的 + 指数，不拉全市场；复权因子变化时只重算受影响标的；游标存 `last_success_date`，失败留缺口待补。
- **[开放问题]** 用户历史文件的具体布局（一天一文件 vs 一标的一文件、列名、代码格式）尚未确认，导入器需以实际样本为准。
- **[开放问题]** 日报中「接近阈值」的判定标准尚未定义。

## 2026-11-16（历史数据样例确认）

- **[事实]** 用户提供两份 2025-02-14 样例：
  - **日 K**：每个交易日一个 UTF-8（含 BOM）CSV，全市场横截面，18 列：`date, code, open, high, low, close, preclose, volume, amount, adjustflag, turn, tradestatus, pctChg, peTTM, pbMRQ, psTTM, pcfNcfTTM, isST`；`adjustflag=3`，即**不复权价**。
  - **因子**：列 `code, dividOperateDate, foreAdjustFactor, backAdjustFactor, adjustFactor`；样例仅 3 行，推断为**当日除权事件清单**而非全市场因子快照。
- **[决策·已定]** 代码格式统一为 `sh.600000` / `sz.000001`。
- **[决策·已定]** **不复权价入库 + 独立因子**，复权在读取时计算，避免因子变更导致价格列全量重写。
- **[决策·已定]** 接近阈值 = 已满足条件但未达阈值，且与阈值相对差距 ≤20%（放量阈值 1.5 时，量比 ≥1.2 计入日报）。
- **[变更]** 进一步撤销 ADR 0001 原决策 3：**不再复制 `parquet_store.py`**，只沿用列 schema 与思路，存储与读写代码自写。ADR 0001 已加修订记录。
- **[开放问题]** 因子文件是「仅当日除权事件」还是「全市场快照」待用户确认为准；若为事件清单，导入需按标的累加成因子时间线，且无事件标的不会出现在文件中。

## 2026-11-18（复权因子口径）

- **[事实]** 依据 BaoStock 官方《复权因子简介》PDF：采用涨跌幅复权法。后复权因子 = 前一天收盘 ÷ 当期前收，上市首日为 1，累积递增；前复权因子 = 当期前收 ÷ 前一天收盘，最近一次除权日后为 1。两者满足 `前复权因子 = 后复权因子 ÷ 最新后复权因子`（用 sh.600000 数据验证：7.128788 ÷ 9.385732 = 0.759535）。
- **[关键事实]** **前复权因子会随每一次新除权被追溯改写**（历史行全变），后复权因子只增不改。
- **[关键事实]** 除权日的 `preclose` 已是调整后昨收（sh.600000 于 2017-05-25 显示 preclose=11.75、前一日 close=15.47），故 `pctChg` 在除权日准确；自行用 `close ÷ 前一日 close` 会算出假暴跌。
- **[决策·已定]** 因子表**只存后复权因子**，前复权按「后复权 ÷ 最新后复权」即时推导；因子表只追加、历史行永不回写。新增 `docs/adr/0005-adjustment-factor-convention.md`。
- **[决策·已定]** 跨日价格比较统一用后复权序列；涨跌幅直接用 `pctChg`；量比不涉及复权。
- **[决策·已定]** P0 四类规则全部为相对指标，**不接受绝对价格阈值**（突破=高于前 N 日最高收盘、超跌=相对前高回撤比例、均线=收盘与 MA(N) 关系、放量缩量=量比），从而避免后复权价与真实价位的换算。
- **[术语]** `GLOSSARY.md` 新增 `量比`、`触发态`、`接近阈值` 三条；现有词条：自选、规则、量比、触发、触发态、预警、日报、接近阈值、持仓（显式排除）。
- **[待办]** spec 已与 ADR 0005 对齐，可进入 `zh-to-tickets`。

## 2026-11-18（因子文件实样统计）

- **[事实]** 统计用户 2026-06-12 因子文件：**92 行、92 个唯一代码、1 个唯一日期**，`foreAdjustFactor` 取值 `1.000000`（多数）与 `0.997093/0.997317/0.997546/0.997619/0.998141`（少数）；`adjustFactor == backAdjustFactor`。
- **[结论]** 该文件是**当日除权标的清单**（非全市场快照）：2025-02-14 仅 3 行（分红淡季），2026-06-12 有 92 行（分红季），行数随除权季波动，符合 A 股规律。
- **[决策·已定]** 后复权因子改由**日 K 推导**：`因子(t) = 因子(t-1) × 昨日不复权收盘 ÷ 当日 preclose`，首日取 1。用 BaoStock 官方示例数值验证成立（15.47÷11.75 = 1.3166 = 9.385732÷7.128788）。
- **[决策·已定]** 因子文件**降级为对账用途**，不作主数据源。关键理由：因子文件必须逐日无缺收集，**漏一天则该日除权事件永久丢失**（后续文件不会重复出现在历史除权事件里），而日 K 横截面可任意重建；且本产品规则全是相对指标，因子基准取 1 不影响判断。
- **[决策·已定]** 导入校验：同一标的后复权因子必须单调不减，违反即报错。
- **[待办]** ADR 0005 已加修订记录；spec 数据层已更新。下一步 `zh-to-tickets`。

## 2026-11-18（单日横截面能否定复权价）

- **[事实]** 统计 2026-06-15 日 K：**5207 行**（全市场）、18 列、`adjustflag` 全为 3（不复权）、无空 close；`tradestatus` 含 0 与 1，其中 **18 只为停牌**。
- **[事实]** 停牌股**在文件中存在**（`tradestatus=0`），其 open/high/low/close/preclose 全部相等、`volume`/`amount` 为空。
- **[结论]** **单日横截面无法确定前/后复权价**：后复权因子是自序列起点累积的量，前复权因子以「最近一次除权」为基准、依赖未来至今的数据。单日文件缺少的正是时间维度。唯一例外是「当日除权且有当日因子文件」的标的（如 2026-06-12 的 92 只），此时前复权因子=1、前复权价=不复权价、后复权价=close×backAdjustFactor。
- **[决策·已定]** 规则求值必须显式排除 `tradestatus=0` 的停牌行，否则量比与均线被空成交量污染；因子推导中停牌行比值为 1，可直接通过。
- **[待办]** spec 数据层已补充停牌处理约定。

## 2026-11-18（取数方案中是否取因子）

- **[确认]** 取数方案**不取复权因子**：历史导入只读用户已有日 K CSV；每日增量只拉自选 + 指数日 K；因子一律由日 K 推导。
- **[理由]** baostock 的 `query_adjust_factor` 是按标的查询，无按日批量接口（用户手上的按日因子文件是自己遍历全市场生成的）；每日对账需约 5200 次请求，而收益只是确认一个已推导出的值。
- **[决策·已定]** 对账只在**历史导入阶段做一次全量比对**，日常不拉因子；增加廉价自检：单次除权因子增量落在 `[0.5, 3]` 之外即告警（A 股最极端送转加分红约 2 出头）。
- **[风险]** 若某日 `preclose` 数据错误，推导因子会跟着错，唯一兜底是上述区间自检与历史导入的一次性全量对账。
- **[澄清]** 「因子可从日 K 完全推导」的前提是**连续序列**；单日横截面缺少昨日 close，无法推导。两者不矛盾，已明确区分。

## 2026-11-18（是否只存后复权数据）

- **[决策·已定]** **不存后复权价，也不存前复权价**。落盘为「不复权 OHLCV + 每行前向填充后的 `back_factor`」。
- **[理由]** 后复权价是派生数据：落盘后真实价不可逆（详情页与通知需要真实价，`sz.000001` 因子 124.9 会把 9 元显示成 1200 元），且源站修正历史因子时整条价格史无法局部修复。存原始价 + 因子则只改一行。
- **[决策·已定]** 因子按**行前向填充**落盘，不用「除权事件表 + 二分查找」；读取时后复权价 = 原始价 × `back_factor`，一次乘法。前复权 = 后复权 ÷ 该标的最新 `back_factor`，不落盘。

## 2026-11-18（每日取数的具体接口）

- **[需求变更]** 用户明确：每日要取**股票数据 + 复权因子数据**，存不复权 + 后复权，舍弃前复权。（较此前「日常不取因子」的表述有调整）
- **[事实·接口]** baostock 三个关键接口：
  - `query_all_stock(day)` → `code, tradeStatus, code_name`（当日证券清单，含名称）
  - `query_history_k_data_plus(code, fields, start, end, frequency="d", adjustflag="3")`，`adjustflag`：**1 后复权 / 2 前复权 / 3 不复权**
  - `query_adjust_factor(code, start, end)` → `code, dividOperateDate, foreAdjustFactor, backAdjustFactor, adjustFactor`，**按标的查、只返回除权日行**
  - 指数日线字段较少：`date,code,open,high,low,close,preclose,volume,amount,pctChg`
- **[决策·已定]** 因子接口**只对疑似除权标的调用**：先用当日 `preclose` 与前一交易日 `close` 比值 ≠ 1 筛出候选（每日通常几只到几十只），再取官方 `backAdjustFactor` 确认。避免全市场 5200+ 次请求。
- **[事实·坑]** baostock 单例长连接、多线程不安全，须串行 + 断点续跑；返回全为字符串、空值为 `""`（停牌股 volume/amount 为空）；`rs.error_code != "0"` 需重新 login。
- **[契约]** lianghua 已有验收锚点：`原始 CSV 价 × 前向填充因子` 须与 baostock 官方 `qfq`/`hfq` 价在浮点误差内一致。

## 2026-11-18（更正：真实接口是按日批量，每日仅两次调用）

- **[纠正·重要]** 上一节关于接口的结论**有误**，以本节为准。baostock 实际使用的是**按日批量接口**（代码依据：`lianghua/script/获取全量数据-日分组.py:82`、`lianghua/script/获取全量增量复权因子.py:96`）：
  - 日线：`bs.query_daily_history_k_AStock(date="YYYY-MM-DD")` → 全市场 A 股当日 18 列
  - 因子：`bs.query_daily_adjust_factor(date="YYYY-MM-DD")` → 当日全部除权标的 5 列（无除权返回空表）
  - 二者都只收 `date` 参数，**每天各调一次即可**，不需要按标的循环。
- **[作废]** 此前「用 `preclose` 比值筛疑似除权标的、再逐只调因子接口」的方案作废；`query_all_stock` 是另一接口（仅 code/tradeStatus/code_name），并非日线数据源。
- **[决策·变更]** 因子口径由「日 K 推导为主」改为「**官方每日清单为准**」，日 K 推导降级为校验与兜底，冲突时以官方值落库并告警。
- **[事实·覆盖缺口]** `query_daily_history_k_AStock` **只含 A 股，不含指数**（已验证样例文件 `2026-06-15.csv` 无 `sh.000001` 等代码）。指数日线需用 `bs.query_history_k_data_plus(...)` 逐只单独取，数量为个位数，故准确表述是「个股 2 次调用 + 指数逐只」。
- **[事实·脚本惯例]** 用户既有脚本以「日期 CSV + 已存在即跳过」实现增量与断点续跑，`utf-8-sig` 编码，空表也写表头文件作为已处理标记。

## 2026-11-19（定稿：只算后复权，不计算前复权）

- **[决策·最终]** **只计算后复权价格，完全不计算前复权**。落盘仅为「不复权 OHLCV + 每行前向填充的 `back_factor`」；展示用不复权价，跨日比较与指标计算统一用后复权价（原始价 × `back_factor`）。前复权不入库、不计算、不对外提供。
- **[依据]** baostock 官方文档（`localdatafactorInfo.md` 第四、五步）同时维护 `foreAdjustFactor` 与 `backAdjustFactor` 两列，但第五步的增量方式是对当日除权标的「删除全部历史因子行 → 重拉全历史替换」。这证明前复权因子必须随新除权整体重写，而后复权重拉后数值不变。存 `back_factor` 可保证历史行永不重写。
- **[事实·接口确认]** 官方文档第二步/第三步确认日线走 `query_daily_history_k_AStock(date=...)`，落 CSV 按年份归档（官方用 gbk 编码，用户脚本用 utf-8-sig）。
- **[待确认]** 官方第六步「计算复权数据」正文因页面截断未获取，尚未核对其填充实现是 `ffill` 还是 `merge_asof`；两者在「长期停牌后复牌」边界可能结果不同。
- **[同步]** spec 数据层已更正：删除「每日增量只拉自选标的」的旧表述，改为全市场批量。

## 2026-11-19（spec 定稿归档）

- **[产物]** `docs/specs/2026-11-16-quant-p0.md`，status `ready-for-agent`，关联 ADR 0001–0005。
- **[修正]** 删除 Further Notes 中「复用 Parquet 存储实现、存在两份副本」的过期表述（与「不复用实现」的决策矛盾）。
- **[新增决策]** 日报走同一套通知接口（ntfy + 邮件兜底），每交易日收盘求值后生成一份，不依赖是否产生预警。
- **[测试 seam]** 定为两个：①规则求值器纯函数（边沿触发/幂等/回落再触发）②HTTP API（自选、规则、预警已读、日报）。数据源适配器不作 seam，用假数据替换。
- **[prior art]** `lianghua/tests/` 的 `test_ingest.py`、`test_datasource_factors.py`、`test_baostock_reconnect.py`、`test_market_api.py`，仅借鉴组织方式，不复用代码。
- **[待办]** 下一步 `/zh-to-tickets`；拆票时须包含「用官方 hfq 价校验 原始价 × back_factor」与「长期停牌复牌 ffill 语义」两项。

## 2026-11-20（tickets 落盘）

- **[产物]** `.scratch/quant-p0/01-…11-…md` 共 11 张 tracer-bullet ticket（每票一文件，front-matter 含 `id/title/status/blocked_by`）。
- **[依赖图]** 01→02→{03,04,05}；05→{06,07,08}；{05,08}→09；{02,05,08,09}→10；07→11。
- **[决策变更]** ADR 0004 分区粒度由「标的+年份」（约 10 万文件）改为「年份单文件」（约 20 文件），按 (标的,日期) 排序写入；每日只重写当年文件。
- **[新增决策]** 每日 API 抓取后归档原始 CSV：CSV 为不可变事实源，Parquet 为可重建的派生索引；重建不需要重新联网（退市股会被数据源移除）。
- **[新增决策]** 查询层用 DuckDB 直读 Parquet，不引入 InfluxDB（只有日线，每年 130 万行，用不到时序库长项）。
- **[数据量基线]** 5200 标的 × 250 交易日 ≈ 每年 130 万行，20 年约 2600 万行。
- **[待办]** 逐票 `/zh-implement`，每票之间 `/clear`。

> 依据：用户「我想重新做这个产品，不再在lianghua和everything上做迭代。」；Agent「Online 只读行情 → 看得懂 → 算得清 → 叫得醒」「如果只能先做一件事，我建议做『自选 + 分级预警 + 预警事后验证』这条最小链路」。

## 2026-11-20（Ticket 02 实现完成）

- **[产物]** Ticket 02 完成并提交 `9e825ca`：`app/storage/{schema,parquet_store,sources,store_state,ingest}.py`、`app/services/data_status.py`、`app/api/data.py`、`app/import_history.py`、`app/daily_update.py`、前端「数据状态」卡片；后端 33 个测试通过。
- **[决策·已定]** 唯一写入口为 `Ingestor.ingest_days`（`ingest_day` 是单日包装）；历史 CSV 与实时接口都产出同一 `DaySnapshot`，只允许这一条写路径。
- **[决策·已定]** 按年份单文件 `<年份>.parquet`，写入用临时文件 + `os.replace` 原子替换；合并时按 (标的, 日期) 去重、后写覆盖。
- **[决策·已定]** 因子事件（除权清单）映射到「当天或之后第一个有日 K 的交易日」，避免某天漏采日 K 时永久丢失除权事件。
- **[术语]** 因子基准（scale）：每个标的首见官方后复权因子时记录的除数，`back_factor = 官方因子 ÷ scale`，使中段导入的序列也从 1 起连续；已写入 `GLOSSARY.md`。
- **[决策·已定]** 校验失败时不得写入 `store_state.json`：`scales` 必须拷贝后使用，否则已推导的基准会被错误落盘。
- **[决策·已定]** 停牌行（`tradestatus=0`）保留入库；停牌日除权无法用「昨收 ÷ preclose」还原增量时，保持原因子并告警，不中断当日写入。
- **[纠正]** 停牌日除权「因子塌回 1」只在 `scale` 缺失（如 store_state 丢失后重建）时发生；`scale` 已存在时官方累积值本身可正确换算，不会塌回。
- **[契约]** `GET /api/v1/data/status` 返回 `totalRows/dateRange/years/missingDates/lastImport`；`lastImport` 含 `tradeDates/rows/replacedRows/source/ranAt/elapsedMs/status/warnings`。`GET /api/v1/data/series?code&start&end` 接受 `sh.600000`/`600000` 等写法，返回归一后的 `code` 与 `backFactor/adjOpen/adjHigh/adjLow/adjClose`。
- **[决策·已定]** 「缺失交易日」= `raw/daily` 已归档但 Parquet 尚无的日期，不引入交易日历，避免把休市日误报为缺失。
- **[待办]** 代码审查提出但本期未做：导入 manifest（重复行、因子缺失标的清单）、增量游标、官方因子与 `preclose` 的全量对账（目前仅在首次见到官方因子时对账）。
- **[待办]** 下一票 Ticket 03（自选）可开始；每票之间 `/clear`。

> 依据：用户「Use Skill: zh-implement」；ticket 02「存在唯一的数据写入入口；任何数据入库都必须经过它，没有第二条写路径」；Agent「33 passed」「写入 5132 行（覆盖 5132 行），耗时 120 ms」。

## 2026-11-24（开发启动脚本）

- **[产物]** 新增 `quant/scripts/start-dev.ps1`：一条命令启动后端（`python -m app`，8000）与前端（`npm run dev`，5173），提交 `535e08b`。
- **[决策·已定]** 两个服务各开独立控制台窗口，关窗即停；不做单窗口后台任务，因为 `Stop-Job` 在 PowerShell 5.1 下不保证杀掉 npm 派生的子进程，易残留占用 5173。
- **[决策·已定]** 脚本启动前检查 venv 与 `node_modules`，缺失即报错退出并给出修复命令；启动后轮询端口最多 30 秒再报告就绪状态。
- **[约束]** 含中文的 `.ps1` 必须存为 UTF-8 **带 BOM**：PowerShell 5.1 按 ANSI 解析无 BOM 文件会把中文读成乱码，并连带吞掉字符串终止符导致语法错误。
- **[开放问题]** 脚本端口硬编码为 8000/5173（与 `config/config.toml`、`vite.config.js` 一致），改配置后需同步修改脚本。

> 依据：用户「编写一个启动前后端的脚本」；Agent「两个服务各在一个独立窗口运行，关闭窗口即停止对应服务」「含中文的 .ps1 必须存为 UTF-8 带 BOM」。

## 2026-11-24（启动脚本改为 bat）

- **[变更]** 启动脚本形式由 `start-dev.ps1` 改为 `quant/scripts/start-dev.bat`，删除 ps1；执行方式变为双击或 `quant\scripts\start-dev.bat`。原因：用户要求。
- **[约束]** 含中文的 `.bat` 必须存为 UTF-8 **无 BOM**，并在首行后 `chcp 65001`；带 BOM 会让 cmd 把首行读成非法命令。
- **[决策·已定]** 保留「独立窗口 + 关窗即停」与「启动前检查 venv / node_modules」的行为；就绪检测用 `netstat` 轮询端口，最多 20 秒。

> 依据：用户「改成bat脚本」；Agent「UTF-8 无 BOM，符合 cmd 要求」。

## 2026-11-24（启动脚本改为 Git Bash 的 sh）

- **[变更]** 启动脚本由 bat 改为 `quant/scripts/start-dev.sh`，删除 bat；用户在 Windows 上用 Git Bash 执行。提交 `1471699`。
- **[偏好]** 用户在 Windows 上使用 **Git Bash** 执行开发脚本，不依赖 cmd 或 PowerShell。
- **[决策·已定]** 不再各开独立窗口：两个服务在同一终端后台运行并输出日志，Ctrl+C 触发 trap 同时停止两者。
- **[约束]** 仓库根新增 `.gitattributes` 固定 `*.sh text eol=lf`：本机 `core.autocrlf=true`，否则 sh 被检出为 CRLF 后 Git Bash 无法执行。
- **[决策·已定]** 停止进程用 `taskkill //F //T //PID $(cat /proc/<pid>/winpid)`，因为只杀 npm 会留下占用 5173 的 node 子进程；端口就绪探测用 bash `/dev/tcp`，不依赖 curl/netstat。
- **[事实·已验证]** 在本机 Git Bash（bash 5.3，Cygwin）下 `/dev/tcp` 探测与 `/proc/<pid>/winpid` 均可用，`npm` 解析为 Git Bash 的 shell shim。

> 依据：用户「你改成shell脚本，我将在windows电脑上使用git bash执行」；Agent「npm=/d/Program/node-v26.13.1-win-x64/npm」「winpid=17976」「8000 未监听（探测可用）」。

## 2026-11-24（Ticket 03 自选管理实现）

- **[决策·已定]** 自选清单与名称字典存放 `data/meta/`（新增配置 `data.meta_dir`，默认 `data/meta`），与可重建的 Parquet 分开。理由：自选是用户数据，不能从原始 CSV 重建；代价：多一个配置项与目录。
- **[决策·已定]** 股票名称来源为 baostock `query_stock_basic` 全市场证券清单（只保留 type=1 股票、status=1 上市），缓存到 `data/meta/stock_names.json`，TTL 1 天；仅在搜索时缓存缺失或过期才刷新。
- **[决策·已定]** 名称刷新失败时退回「只按代码搜索」已入库标的，搜索响应 `namesAvailable=false`，不阻断自选增删；代价：失败期间名称显示为空（前端显示「—」）。
- **[决策·已定]** 自选列表涨跌幅直接取数据源 `pctChg`，不由 `close/preclose` 反算；停牌由后端返回 `suspended` 标记，前端显示「停牌」，不改写源数值。
- **[契约]** 新增 `GET /api/v1/watchlist`、`POST /api/v1/watchlist`、`DELETE /api/v1/watchlist/{code}`、`GET /api/v1/stocks/search?q&limit`；自选条目为 `code/name/addedAt/date/close/pctChg/suspended`；搜索返回 `items/count/namesAvailable`；重复加入返回 `created=false`，删除不存在返回 `removed=false`，均不报错。
- **[产物]** Ticket 03 完成并提交 `c9222b5`；后端 44 个测试通过，前端 `npm run build` 通过；用真实 Parquet 冒烟验证 `sh.600000` 最新交易日 2026-06-15、收盘 9.53、`pctChg` -1.4478。
- **[风险]** 名称字典依赖 baostock 网络；离线或未安装 baostock 时名称不可用，仅能按代码搜索与添加。

> 依据：用户「Use Skill: zh-implement」；ticket 03「可按代码或名称搜索标的并加入自选」「涨跌幅直接使用数据源的涨跌幅字段」「自选数据持久化，服务重启后仍存在」；Agent「自选是用户数据，不能像 Parquet 那样从原始 CSV 重建」「名称字典不可用时退回只按代码搜索」。

## 2026-11-24（Ticket 03 双轴代码审查）

- **[开放问题]** `data/meta/` 下 `watchlist.json` 与 `stock_names.json` 的写入是否算违反「所有入库必须经过 `Ingestor`」；`quant/AGENTS.md` 未豁免用户数据，字面冲突，待用户拍板。
- **[风险]** `load_watchlist` 解析失败时静默返回空清单，下次写入会覆盖损坏文件，存在自选数据无提示丢失的风险；与「不做静默兜底」相悖。
- **[风险]** `StockDirectory.ensure()` 只捕获 `IngestError`；baostock 抛出的其它异常会冒到接口成为 500，与 docstring「刷新失败退回旧缓存」不符。
- **[待办]** 审查提出但未修：搜索不支持 `sh600000` / `600000.SH` 写法；空查询返回 `namesAvailable=true` 与字典实际可用性无关；停牌仅在前端显示「停牌」，后端仍返回 `pctChg=0`；名称字典未排除 B 股等非 A 股代码段；未入库标的加入自选后五列行情全空且无「尚无本地数据」提示。
- **[事实·已验证]** 涨跌幅取源字段、重复加入幂等且保持顺序、空态引导、原子写、响应 `{code,message,data}` + camelCase 均通过审查。

> 依据：用户「Use Skill: zh-code-review」；Standards 子代理「唯一需拍板的是 meta 文件写入是否算另开写路径」；Spec 子代理「自选文件损坏时静默清空并可被覆盖」。

## 2026-11-24（Ingestor 边界澄清）

- **[纠正]** `quant/AGENTS.md` 的「所有入库都必须经过 `Ingestor`」中的「入库」指**行情数据**入库（原始 CSV → Parquet），不是所有文件落盘；`data/meta/` 下的自选清单与名称字典不属于行情数据，由各自的 store 原子写入。
- **[开放问题]** `quant/AGENTS.md:39` 的措辞未限定范围，是否改为「所有**行情数据**入库都必须经过 `Ingestor`……」待用户确认；仅文档改动，不影响代码。

> 依据：用户「这个你再解释一下，Ingestor 是什么」；Agent「Ingestor 的输入契约是 `DaySnapshot`……自选是代码列表、名称是字典，没有日期/OHLC/因子，塞进 Ingestor 属于错误抽象」。

## 2026-11-24（AGENTS 边界措辞改正）

- **[决策·已定]** `quant/AGENTS.md` 改为「所有**行情数据**入库都必须经过 `Ingestor`，不得另开行情写路径」，并补一句「`data/meta/` 下的用户数据与字典缓存不属于行情数据，由各自的 store 原子写入」。提交 `dd04173`；仅文档改动。

> 依据：用户「改正文档」；Agent「所有**行情数据**入库都必须经过……`data/meta/` 下的用户数据与字典缓存不属于行情数据」。

## 2026-11-24（ensure 兜底范围分析）

- **[纠正]** 「baostock 断网会让 `ensure()` 抛非 `IngestError` 导致 500」不成立为通例：常见断网时 `send_msg()` 的 `except Exception` 会吞掉网络异常并返回 `None`，现有代码已转成 `IngestError`；真正会逃逸的是 `SocketUtil.connect()` 中 `mySockect` 未绑定引发的 `UnboundLocalError`、残缺回包解析的 `IndexError`、`finally: bs.logout()` 抛出的异常（并会覆盖原 `IngestError`）、以及 `_write_cache()` 的 `OSError`。
- **[开放问题]** `StockDirectory.ensure()` 兜底范围怎么改未决：方案 A 在 `ensure()` 捕获 `Exception` + `logger.warning` 退回旧缓存（推荐）、方案 B 在 `BaostockNameProvider.fetch_names()` 统一包成 `IngestError`、或暂不改。用户答「先不要动代码，我先看看」，代码未改动。

> 依据：用户「可能违规：stock_names.py 的 `ensure()` 只捕获 `IngestError`……这一条具体解释一下，我看看应该如何修改」；Agent「这条不是『断网必 500』，而是『兜底承诺不严密』」；用户「先不要动代码，我先看看」。

## 2026-11-24（ensure 兜底方案 A 实施）

- **[决策·已定]** 采用方案 A：`StockDirectory.ensure()` 捕获 `Exception`（不捕获 `BaseException`），`logger.warning` 记录后沿用旧缓存/空字典。理由：名称字典是尽力而为的外部依赖，`refresh()` 可能抛 `UnboundLocalError`、`IndexError`、`bs.logout()` 异常与 `_write_cache()` 的 `OSError`，不应冒到接口变 500。放弃方案 B（provider 统一转 `IngestError`）：覆盖不到 `_write_cache`，且需重构 `finally: bs.logout()` 以免掩盖原异常。代价：掩盖非预期编程错误的可见性，靠 warning 日志兜底。新增两条 `RuntimeError` 测试（搜索退回按代码搜索、`POST /watchlist` 仍 200），全量 `pytest -q` 46 passed。提交 `68045a7`。

> 依据：用户「按方案 A 修改代码」；Agent「`except Exception as exc:  # 名称字典是尽力而为的外部依赖，失败不应阻断自选与搜索`」。

## 2026-11-24（四项审查判断项解释）

- **[风险]** `meta_dir` 与既有 `raw_dir` / `parquet_dir` 一样只做路径解析、不做可写性校验；`save_watchlist` 的 `OSError` 在 `POST /watchlist` 未被捕获，会走 FastAPI 默认 500 并破坏 `{code,message}` 错误体。
- **[开放问题]** `watchlist.json` 解析失败时 `load_watchlist` 静默返回空清单，下一次 `POST /watchlist` 会用原子替换覆盖损坏文件且无备份；是否改为「严格报错」「改名备份 + 日志告警」或维持现状，待用户决策。
- **[开放问题]** `api/watchlist.py` 用 `str(exc)` 透出 `IngestError` 文案，与 `data.py` 的固定文案不一致；`DELETE /watchlist/{code}` 在 API 与 service 各调用一次 `normalize_code`；两者是否统一待决策。搜索对 `sh600000` 不命中属于子串匹配问题，与双重归一无关。
- **[开放问题]** `StockDirectory`（实为名称缓存）、`ensure()`、`_present` 命名是否调整待决策。

> 依据：用户「判断项：watchlist_store.py 在 JSON 损坏时静默返回空清单……做详细解释，解释完我看过后再决策如何修改」；Agent「损坏只会在下一次 `POST /watchlist` 落盘时被覆盖，删除不会触发写盘」。

## 2026-11-24（四项审查判断项决策与实施）

- **[决策·已定]** 自选文件损坏改为显式报错：新增 `WatchlistCorruptError`，仅「文件不存在」返回空清单，解析失败或结构非法抛错；`create_app` 注册 handler 映射 500 并保留原文件，不再用空清单覆盖用户数据。提交 `6d2b67f`。
- **[决策·已定]** 启动时在 `create_app` 对 `raw_dir` / `parquet_dir` / `meta_dir` 统一探测可写（`mkdir` + 写临时探针文件后删除），失败抛 `RuntimeError` 并指出目录。代价：`create_app` 带建目录副作用。
- **[决策·已定]** 错误文案在 API 层固定为「标的代码格式应为 sh.600000 / sz.000001」，不再用 `str(exc)` 透出存储层消息；`remove_from_watchlist` 改为返回 `(归一化代码, removed)`，删除接口不再重复归一。
- **[决策·已定]** 命名调整：`StockDirectory` → `StockNameCache`，`app.state.stock_directory` → `app.state.stock_names`，`create_app(stock_names=...)`；`_present` → `_to_item`；`ensure()` 保留原名。验证：`pytest -q` 48 passed。

> 依据：用户「1:按推荐 2：启动时探测 3a：固定文案 3b：按推荐改 4：按推荐」；Agent「自选文件损坏或不可读：<path>」「启动时验证数据目录可写，避免问题拖到首次写入才暴露」。

## 2026-11-24（五项疑似问题核查）

- **[纠正]** 「停牌语义只有 Web 端能拿到」不成立：`ParquetStore.latest_bars` 由 `tradestatus == 0` 产出 `suspended`，`_to_item` 已把该字段随响应返回；Web 只是消费它渲染「停牌」。`pctChg=0` 是源字段原值，符合「停牌只加标记、不改写数值」的既定口径。
- **[纠正]** 「自选文件损坏静默清空」已在提交 `6d2b67f` 修复：`load_watchlist` 抛 `WatchlistCorruptError`，工厂映射 500 并保留原文件，有测试 `test_corrupt_watchlist_is_reported_and_not_overwritten`。
- **[开放问题]** 搜索不支持 `sh600000` / `600000.SH`（按子串匹配 `sh.600000`）；空查询固定返回 `namesAvailable=true`；名称字典仅按 `type=1/status=1` 过滤，未排除 B 股（`sh.900*` / `sz.200*`）。三项是否修待用户决策。

> 依据：用户「检查这几项 疑似实现有误」；Agent「`suspended` 已在响应里」「`stock_names.py` 的过滤只有 `type=1` 与 `status=1`，B 股也是 `type=1`」。

## 2026-11-24（搜索写法与空查询修复）

- **[决策·已定]** 搜索先尝试 `normalize_code`，归一成功则增加「代码完全相等」匹配，失败保留原有子串匹配；`sh600000` / `600000.SH` 与加入接口口径一致，部分代码搜索不受影响。提交 `b3fa22f`。
- **[决策·已定]** 空查询的 `namesAvailable` 改为 `bool(stock_names.names())`，只读磁盘缓存、不触发联网刷新。提交 `b3fa22f`；验证 `pytest -q` 49 passed。
- **[决策·暂定]** 名称字典排除 B 股（`sh.900*` / `sz.200*`）暂不改，用户「先不改」；已知这些代码会进入名称字典。

> 依据：用户「2、原生日切片 code 为 sh.xxxx sz.xxx 形式……3、改 4、先不改」；Agent「搜索与加入两个接口的入参口径不一致」。

## 2026-11-25（项目进度盘点）

- **[事实]** 11 张 ticket 中 01 骨架、02 历史导入与按年存储、03 自选管理为 `done`，04–11 全部 `todo`；后端 `pytest -q` 49 passed。
- **[事实]** 历史原始数据在 `G:\各种资料\量化数据\data\raw`：`daily/` 与 `factor/` 各 8770 个 CSV，覆盖 1990-12-19 ~ 2026-11-24，日 K 均为 18 列且结构一致；`market/`（配置的 `parquet_dir`）为空，真实全量历史**尚未导入 Parquet**。
- **[风险]** 目录名与代码约定不一致：用户目录为 `raw/factor`（单数），`HistoricalCsvSource` 约定 `factors/`（复数），直接执行 `python -m app.import_history` 会读不到除权清单，导致全历史 `back_factor` 全为 1、跨除权比较失真。
- **[事实]** 每日实时取数已具备：`RealtimeSource` + `BaostockFetcher`（`query_daily_history_k_AStock` / `query_daily_adjust_factor`），抓取后归档原始 CSV 再入库；入口为手动命令 `python -m app.daily_update [YYYY-MM-DD]`，默认取当天。
- **[风险]** 每日取数无自动调度（ticket 10 未做），失败留缺口需手动按日期重跑；全市场日 K 接口不含指数，指数不在当前覆盖范围。
- **[风险]** 全量历史导入规模约 30M 行（8770 交易日 × 约 5200 标的），按年分批执行，耗时与内存尚未实测。

> 依据：用户「现在整个项目到什么进度了……1、数据采集做好了吗 2、数据存储做好了吗 3、日切片csv导入parquent做好了吗 4、获取每日新数据做好了吗」；Agent「11 张 ticket 完成 3 张」「market/ 为空」「代码约定 factors/，实际目录是 factor」。

## 2026-11-25（历史导入空值、停牌口径、因子策略）

- **[纠正]** 停牌口径是 `tradestatus == 0`，不是 `amount == 0`。实测全历史 1871 万行：停牌 587,367 行、amount=0 578,531 行，其中非停牌但 amount=0 有 7,927 行、停牌但 amount 为空 556 行（抽样），两者不等价。`latest_bars` 生成 `suspended` 用的就是 `tradestatus`。
- **[决策·已定]** 停牌行允许价格为空：全历史仅 3 行（`sz.000022` 2018-12-26、`sz.000043` 2019-12-16、`sz.300114` 2025-02-17）整行无报价且 `tradestatus=0`，原校验强制 open/close 非空导致整年导入失败；现只对 `tradestatus != 0` 的行强制价格齐全，且这类行不作为「上一交易日」基准。
- **[决策·已定]** 除权目录名兼容 `factors/` 与 `factor/`（用户实际数据为 `factor/`）。此前 8770 个除权文件被静默忽略，存量 `back_factor` 全为 1.0（2017 年 799,801 行实测 min=max=1.0）。
- **[变更]** 推翻「后复权因子必须单调不减、单次增量在 [0.5, 3] 内，否则拒绝写入」的硬校验 → 新策略「信任数据源官方 `backAdjustFactor`，回退与超常规增量只记告警」。原因：实测 60,510 个事件相邻对中有 60 处回退、159 处增量 > 3（90 年代拆股、2015–2017 高送转），硬校验导致 1991–2006、2008–2026 各年导入全部失败。用户选择「信任官方值，异常只告警（推荐）」。
- **[纠正]** `scale`（因子基准）从未持久化：`_build_frames` 推导的 scales 未写回 `store_state`，导致每次 `ingest_days`（按年分批）都重新推导基准，产生大量非数据源原因的「回退」告警。现改为整批写入成功后 `state.scales = scales` 再 `save_state`，失败时仍不落盘。
- **[决策·已定]** 清空 `G:\各种资料\量化数据\data\market` 下的 Parquet 与 `store_state.json` 后全量重导（用户选择「清空 Parquet 重新全量导入」）。
- **[事实]** 重导完成：37 个年度文件、18,714,772 行、5,566 个标的、1990-12-19 ~ 2026-11-24；`scales` 5,566 条已落盘；`back_factor != 1.0` 行 17,662,129，min 0.62929 / max 10765.42；`pytest -q` 50 passed。
- **[风险]** 官方因子存在真实跳变，已按官方值接受并只告警，例如 `sz.000002` 2025-01-09 回退 135.886551→134.284605（当天无分红，疑为数据源毛刺）、`sh.600652` 1993-03-15 单次增量 177.7778；这些位置的后复权价会有跳变。缓解方式仅为告警（告警量：早期年份每年 1–27 条）。
- **[开放问题]** `Ingestor.import_history` 的 docstring 写「一年失败不影响其他年份」，但循环内未捕获异常，实际某一年的 `IngestError` 会中断整段导入；本轮未改。

> 依据：用户「导入失败：2018-12-26.csv 的 open 存在空值或非数字」「怎样判断停牌的？amount列=0？」「信任官方值，异常只告警（推荐）」「清空 Parquet 重新全量导入（推荐）」；Agent「全历史里只有 3 行是价格全空，且全部是停牌日」「scales 从来没有被写进 store_state」「36 年 0 失败」。

## 2026-11-25（除权清单改为按年存储）

- **[决策·已定]** 除权清单从「每日一个 CSV」改为「每年一个 CSV」：`factor/YYYY.csv`，5 列同源格式。理由：8770 个文件合计仅 3.65 MB、6.6 万行，痛点是每次 `HistoricalCsvSource` 初始化都要打开全部文件。用户选择「一年一个 CSV」。
- **[决策·已定]** 读取按年懒加载并缓存：加载年 Y 时同时读 Y 与 Y-1 的文件，保证「上一年末事件落到下一年第一个交易日」不丢；旧的 `YYYY-MM-DD.csv` 仍然兼容。日 K 仍按日存（单年几十 MB，按年存每天重写不划算）。
- **[决策·已定]** 存量 8770 个按日文件合并为 37 个年文件后移入 `raw/factor_daily_backup/`，不直接删除（用户选择「合并后移到备份目录」）。
- **[事实]** 迁移结果：66,227 行去重后行数不变（无重复），1990–2026 共 37 个年文件；迁移前后用 `HistoricalCsvSource` 逐日比对的「交易日 → 除权事件」完全一致（6434 个交易日、66,227 个事件）。
- **[纠正]** `RealtimeSource` 原先固定写 `raw_dir/factors/`，而历史数据在 `factor/`；按新读取逻辑 `_factor_dir` 优先 `factors/`，会新建第二套目录并让历史事件「消失」。现统一改为 `_factor_dir(raw_dir)`，写进已存在的目录。
- **[契约]** 年文件写入流程：读当年文件 → 合并当日事件（`code + dividOperateDate` 去重，后到的为准）→ 临时文件 + `os.replace` 原子替换；若当年文件已含该交易日事件，则沿用归档结果并告警，不用本次抓取覆盖。
- **[风险]** 年文件每天被重写，不再保持「每个归档文件写入即不可变」；内容层面仍是追加语义（去重保证历史行不被删除），但人工误编辑或写入中断会污染整年数据，原子替换是唯一保护。
- **[事实]** 端到端验证：迁移后重导 2018 年成功（857,532 行、状态 ok）；`pytest -q` 52 passed（新增按年文件读取、跨年事件落点两个用例）。

> 依据：用户「现在因子数据每天都存储了一个csv，这个能不能按年存储」「一年一个 CSV（推荐）」「合并后移到备份目录（推荐）」；Agent「8770 个日文件，合计只有 3.65 MB」「迁移前后逐日比对完全一致」「日 K 的 daily/ 不建议一起改」。
