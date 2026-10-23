# TradeTrace App

证券交易记录应用，React Native + Expo 实现，同一套代码运行在 **Web 浏览器** 与 **Android** 上。属于 TradeTrace 项目（与 `lianghua` 量化平台合并后的交易记录端）。

## 技术栈

| 层 | 选型 |
|---|---|
| 框架 | Expo SDK 58 / React Native 0.88 / React 19 |
| 路由 | Expo Router（`src/app` 文件式路由） |
| 语言 | TypeScript（strict） |
| 状态 | React Context + 纯函数状态变换 |
| 本地存储 | AsyncStorage（Web 走 localStorage，Android 走原生存储） |
| 测试 | Vitest（领域统计逻辑，纯 TS 无原生依赖） |

## 启动

```bash
npm install
npm run web        # 浏览器访问 http://localhost:8081
npm run android    # 需要 Android 模拟器或已连接设备（Expo Go / 开发构建）
```

其他命令：

```bash
npm run typecheck  # tsc --noEmit
npm run test       # vitest run
npm run export:web # 导出静态站点到 dist/
```

本机未安装 Android SDK，Android 端当前通过 **Expo Go 扫码** 验证；需要独立 APK 时使用 EAS Build。

## 已实现功能

- 账户管理（增 / 删，删除级联清理股票、交易、做T）
- 账户下的股票管理（增 / 改 / 删）
- 股票交易流水：买入、卖出、股息；编辑、删除；预期价格区间按比例自动换算
- 做T关联：卖出记录关联买入份额，按份额比例分摊手续费计算收益
- 收益统计：按账户 / 按个股 / 合并账户 / 按做T 四个维度
- 坚果云 WebDAV 同步：上传本机数据到云端、按「远程设备 ID」下载覆盖本机

统计口径与旧版 Flutter 应用保持一致，见 `src/data/stats.ts`。

## 目录

```
src/
  app/                      # Expo Router 路由（页面）
    _layout.tsx             # 根布局 + TradeProvider
    index.tsx               # 账户总览
    accounts.tsx            # 账户管理
    summary.tsx             # 收益统计
    settings.tsx            # 应用设置（坚果云 WebDAV 同步）
    account/[id].tsx        # 账户详情（股票列表）
    stock/[id].tsx          # 个股详情（交易流水 / 做T）
  components/
    ui.tsx                  # 基础组件（卡片、按钮、弹层、表单控件）
    forms.tsx               # 交易 / 做T 表单
  data/
    types.ts                # 领域模型
    state.ts                # 纯函数状态变换（增删改 + 级联）
    stats.ts                # 汇总与收益统计
    storage.ts              # 本地持久化（唯一需要替换的后端接入点）
    sync-config.ts          # 坚果云同步配置（设备 ID / 账号 / 应用密码）
    webdav.ts               # WebDAV PUT / GET / MKCOL 客户端
    sync.ts                 # 同步文件序列化与上传下载
    trade-context.tsx       # Provider + actions
    stats.test.ts           # 领域逻辑测试
    sync.test.ts            # 同步配置 / WebDAV 编码 / 同步文件测试
  theme/tokens.ts           # 颜色、间距、字号
  utils/format.ts           # 数字 / 日期格式化
```

## 与 lianghua 后端的对接状态

**尚未开始对接**，当前数据只存在本机 `AsyncStorage`。对接时：

1. 新增 `src/data/api.ts`，在 `src/data/storage.ts` 同层替换加载/保存实现。
2. 领域模型（`types.ts`）直接作为 API DTO 的基础，页面与统计逻辑不需要改动。
3. lianghua 后端改动在独立分支进行，本仓库暂不触碰 `lianghua/`。

## 坚果云同步

在与 lianghua 后端对接之前，用坚果云 WebDAV 替代云同步（逻辑沿用旧 Flutter 版本，文件改为 JSON）：

- 云端路径：`TradeTrace/{上传方设备ID}/tradetrace.json`
- 上传：把当前全部账户、股票、交易、做T关联写入云端
- 下载：读取「远程设备 ID」对应目录的文件，校验格式后整体替换本机数据
- 配置（含应用密码）仅保存在本机 AsyncStorage，不随同步文件上传
- Web 端受浏览器跨域（CORS）限制，坚果云 WebDAV 通常无法直连；Android 端正常

## 说明

- 应用已移除旧版 Flutter 工程中的「密码管理」；坚果云同步保留并改写为 RN 实现。
- 既有 Flutter 数据（`stock_trading.db`）不迁移，新系统从零开始。
