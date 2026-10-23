# TradeTrace / everything — 开发规则

Expo + React Native 交易记录应用，同一套代码同时支持 **Web 浏览器** 与 **Android App**。
本目录是 `TradeTrace` monorepo 的一部分：`lianghua/` 是 Python + FastAPI 量化后端，**当前阶段不要修改 `lianghua/` 下任何文件**，也不要主动开始前后端对接。

## Expo 版本会持续破坏兼容 —— 不要凭记忆写 API

Expo 每个 SDK 都会重命名、移动或移除 API。改动任何 Expo / EAS / React Native API 之前：

1. 先读 `package.json` 中 `expo` 的主版本号（当前 `58`）。
2. 打开对应版本文档：`https://docs.expo.dev/versions/v58.0.0/`
3. 其他问题查 https://docs.expo.dev/llms.txt，顺着链接读具体页面，不要凭记忆作答。

## 常用命令

Windows PowerShell 禁止运行 `.ps1`，必须用 `npm.cmd` / `npx.cmd`：

```bash
npm.cmd install                 # 安装依赖
npm.cmd run web                 # Web 开发服务器（http://localhost:8081）
npm.cmd start                   # Expo 开发服务器（Expo Go 扫码跑 Android）
npm.cmd run android             # 本地原生 Android（需 Android SDK）
npm.cmd run typecheck           # tsc --noEmit
npm.cmd run test                # vitest run
npm.cmd run export:web          # 静态 Web 构建
npx.cmd expo export -p android  # Android bundle 构建验证
npx.cmd expo install <pkg>      # 新增依赖只能用它，保证 SDK 版本兼容
npx.cmd expo install --check    # 检查依赖版本是否匹配 SDK
```

## 项目结构

```
everything/
├── app.json                 # Expo 配置（包名、splash、typedRoutes、web 输出模式）
├── package.json             # 脚本与依赖
├── src/
│   ├── app/                 # Expo Router 路由，只有这里放页面
│   │   ├── _layout.tsx      # 根布局：SafeAreaProvider + TradeProvider + Stack
│   │   ├── index.tsx        # 账户总览（累计收益、账户列表）
│   │   ├── accounts.tsx     # 账户管理
│   │   ├── account/[id].tsx # 账户详情（股票列表）
│   │   ├── stock/[id].tsx   # 个股详情（交易流水、做T关联）
│   │   ├── summary.tsx      # 收益统计（账户/个股/合并/做T）
│   │   └── settings.tsx     # 应用设置（坚果云 WebDAV 同步）
│   ├── components/
│   │   ├── ui.tsx           # 设计系统组件：Screen/TopBar/Card/Field/Button/Sheet/ConfirmDialog…
│   │   └── forms.tsx        # 交易表单、做T表单
│   ├── data/                # 领域层，纯 TS，可单测
│   │   ├── types.ts         # Account/Stock/TransactionTrade/TTrade/TradeState
│   │   ├── stats.ts         # 收益统计口径（唯一权威实现）
│   │   ├── state.ts         # 增删改与级联删除（纯函数）
│   │   ├── storage.ts       # AsyncStorage 持久化（未来接 lianghua 的唯一替换点）
│   │   ├── trade-context.tsx# React Context + 持久化
│   │   ├── sync-config.ts   # 坚果云配置（设备 ID、账号、应用密码）
│   │   ├── webdav.ts        # WebDAV PUT/GET/MKCOL 客户端
│   │   └── sync.ts          # 同步文件序列化与上传下载
│   ├── theme/tokens.ts      # 颜色、间距、圆角、字体
│   └── utils/               # format.ts（数字/日期）、navigation.ts（goBack）
├── docs/                    # AI 规划与执行文档
│   ├── plans/               # 规划文档（实施计划、任务拆解）
│   └── execution/           # 执行文档（执行记录、验证结果）
└── README.md                # 面向使用者的说明
```

约定：

- **只有 `src/app/` 下的文件是路由**，组件、hooks、工具一律放在 `src/app/` 之外。
- 路径别名 `@/*` 指向 `src/*`。
- 统计逻辑只能写在 `src/data/stats.ts`，页面只负责展示，不得在页面里另行计算收益。
- 数据读写统一走 `TradeProvider` 的 `actions`，页面不要直接调用 `storage.ts`。

## AI 规划文档与执行文档

AI 产生的规划文档与执行文档**统一存放在本项目的 `docs/` 目录内**，不得散落在项目根、`src/` 或临时目录：

| 文档类型 | 存放位置 | 内容 |
|---|---|---|
| 规划文档 | `docs/plans/` | 需求澄清结论、实施计划、任务拆解、涉及文件与验证方式 |
| 执行文档 | `docs/execution/` | 执行记录、逐步核对结果、实际验证命令与输出、遗留问题 |

- 命名：`YYYY-MM-DD-<简短主题>.md`；同一任务的规划与执行文档**同名成对**。
- 执行文档末尾必须包含「验证结果」一节，写明实际跑过的命令与结果，不得只写“已完成”。
- 规划/执行文档随代码纳入 git；临时草稿、构建产物、截图不入库。
- `docs/` 只放文档，不放源码或测试数据。

## 领域口径（改动前必读）

- `shares` 正数 = 买入，负数 = 卖出；股息记录 `shares = 0`，`dividend` 为金额。
- 单笔费用：`cost = -price * shares - commission`；股息 `cost = dividend`。
- 建仓周期：持有股数由 0 变正开始新周期，回到 0 时结算并重置；做T手续费按关联份额比例分摊到卖出笔。
- 个股六项：持有股数、持仓成本、持仓收益、总成本、总收益、清仓收益。
  - 持仓成本 = |当前周期累计费用 ÷ 持有股数|
  - 持仓收益 = 当前周期累计费用（净现金流，买入为负）
  - 总成本 = |累计费用 ÷ 持有股数|，总收益 = 累计费用
  - 清仓收益 = 总收益 − 持仓收益，**全部股息直接计入清仓收益**，不参与当前周期摊薄
- 任何口径变更必须同步改 `stats.test.ts`，并说明对其它指标的影响。

## 开发标准

- TypeScript strict，不允许 `any` 逃逸（确需时写明原因）；不保留未使用变量/导入。
- 复用 `src/components/ui.tsx` 的既有组件与 `tokens.ts` 的样式常量，不要在页面里写零散的魔法数字。
- 依赖新增一律用 `npx.cmd expo install`；能用 Expo 官方模块就不要引第三方库。
- 不手工创建或编辑 `android/`、`ios/` 目录（由 CNG 生成），原生配置改 `app.json`。
- 密码管理等旧功能已移除，不要恢复；坚果云同步必须保留，且不得把应用密码写入同步文件。
- 暂不接 lianghua 后端；若需预留，只能通过 `storage.ts` 抽象层，不得在页面里直接发请求。
- 面向用户的文案与代码注释使用中文。

## 测试标准

- 领域逻辑（`src/data/*.ts`）必须有 Vitest 用例，覆盖正常路径 + 边界（清仓重开仓、手续费分摊、股息时点、非法输入）。
- 测试文件与被测文件同目录，命名 `*.test.ts`；测试只依赖纯 TS，不引入 RN 原生模块。
- 每个 bug 修复先补一条能复现的用例，再改实现。
- 不写“只跑得通”的假测试（不断言、只 snapshot 空实现）。

## 交付验证标准

完成任务前必须**实际执行**以下检查，未执行不得声称完成：

1. `npm.cmd run typecheck` —— 0 error。
2. `npm.cmd run test` —— 全部通过，并确认新增逻辑有用例覆盖。
3. `npm.cmd run export:web` —— 构建成功。
4. `npx.cmd expo export -p android` —— Android bundle 构建成功（本机无 Android SDK 时以此代替真机编译）。
5. 涉及 UI 的改动：启动 `npm.cmd run web`（或 `expo export -p web` + 静态服务器），在浏览器实测受影响页面：渲染、交互、空状态、保存后刷新是否持久化，并确认 console 无报错。
6. 涉及同步的改动：至少验证配置保存与持久化、按钮禁用逻辑、二次确认弹窗；真实 WebDAV 上传/下载需在 Android 端或用真实坚果云账号验证，Web 端受 CORS 限制属已知情况。
7. 结构或口径变化时同步更新 `README.md`。
8. 汇报时给出实际命令结果（用例数、构建状态），不要只说“已通过”。
