---
name: minimum-viable-dev
description: "强制 AI 在编写代码前进行最小可行开发决策检查。在实现任何功能前必须依次回答：Does this need to exist? / Already in this codebase? / stdlib does it? / Native platform feature? / Installed dependency? / One line? → Only then: the minimum that works."
---

# Minimum Viable Development (最小可行开发)

## Overview

**核心原则：** 在 AI 编写任何代码之前，强制进行最小可行开发决策链检查，从根源上杜绝过度开发（over-engineering）。

无论是新增功能、修复 Bug、还是构建组件，在写第一行代码之前，必须先依次回答以下 7 个问题：

## 决策链（The Seven Gates）

### Gate 1: Does this need to exist?
> 这个东西真的需要存在吗？

- 当前需求是否真的需要新增代码/功能？
- 是否可以通过调整现有逻辑实现？
- 是否用户真正需要，还是只是"以防万一"？

### Gate 2: Already in this codebase?
> 代码库里是不是已经有了？

- 项目里有没有现成的函数/组件/工具能用？
- 换个参数、改个调用方式是否能满足需求？
- 搜索关键词：同一模块、相近命名、类似逻辑

### Gate 3: stdlib does it?
> 语言标准库能搞定吗？

- Python：`os`, `pathlib`, `itertools`, `collections`, `json`, `datetime`, `re`...
- Node.js / JS：`fs`, `path`, `url`, `util`, `EventEmitter`, `crypto`...
- 其他语言同理

### Gate 4: Native platform feature?
> 平台原生功能就支持？

- 浏览器：`fetch`, `URL`, `IntersectionObserver`, `ResizeObserver`, `Intl`, `navigator.clipboard`, CSS `container queries`...
- Node.js：原生支持的模块和 API
- 移动端/桌面端平台的内置能力

### Gate 5: Installed dependency?
> 已安装的依赖里就有？

- `package.json` / `requirements.txt` / `go.mod` 里已有但没用过的功能？
- 仅需 import 一行就能用，为什么要自己写？

### Gate 6: One line?
> 一行代码就能解决？

- 一个表达式、一个 utils 调用、一行 CSS ？
- 如果一个工具函数只封装了一行逻辑 → 直接在调用处写，不要抽离

### Gate 7: Only then: the minimum that works
> 只有通过以上 6 关 → 才开始写，且只写最小可行实现

- 仅实现当前需求所需的最少代码
- 不要"顺带优化"、"提前抽象"、"预判未来需求"
- 不写当前不需要的配置/参数/接口

## 工作流程

### 在每次开始代码实现前：

1. **停顿** — 拿到需求后，不要立即写代码
2. **逐门检查** — 按顺序回答以上 7 个问题，每一步都必须明确输出
3. **记录决策** — 将检查结果写入当前的上下文/注释中
4. **未通过** → 使用已有方案，不写新代码
5. **全部通过** → 只写最小可行实现

### 输出模板

在每次实施前，输出如下格式：

```
## 最小可行决策检查

| # | Gate | 结果 | 说明 |
|---|------|------|------|
| 1 | Does this need to exist? | ✅ / ❌ | ... |
| 2 | Already in this codebase? | ✅ / ❌ | ... |
| 3 | stdlib does it? | ✅ / ❌ | ... |
| 4 | Native platform feature? | ✅ / ❌ | ... |
| 5 | Installed dependency? | ✅ / ❌ | ... |
| 6 | One line? | ✅ / ❌ | ... |
| 7 | Only then: minimum | ✅ / ❌ | ... |

**结论：** 需要写新代码 / 不需要写新代码
```

## 触发器（When to Invoke）

- **必须执行**：新增功能、创建组件/模块、写工具函数、加配置文件
- **建议执行**：修复 Bug（先确认是否真的需要修改）、重构、优化
- **跳过**：纯文案/文档修改、单纯重命名、仅 CSS 样式调整（不影响逻辑）

## 常见违规模式

| 违规行为 | 示例 | 正确做法 |
|---------|------|---------|
| 封装一行函数 | `const isEven = (n) => n % 2 === 0` | 直接写 `n % 2 === 0` |
| 重复造轮子 | 自己写深拷贝 | 用 `structuredClone` / `JSON.parse(JSON.stringify())` |
| 过度抽象 | 为单一用法写泛型/接口 | 保持 inline |
| 提前优化 | 给不存在的并发场景加锁 | 不加 |
| 预判需求 | 加当前不需要的配置项 | 不加 |
| 多余依赖 | 装 lodash 就为了 `_.get` | 用可选链 `?.` |
| 过度配置 | 把简单工具脚手架化 | 保持简单 |

## 设计思路

这个 Skill 的设计哲学来自以下理念的融合：

- **YAGNI** (You Ain't Gonna Need It) — 不要为未来可能的需求买单
- **KISS** (Keep It Simple, Stupid) — 最简单的方案往往是最好的
- **最小可行产品思维** — 每次交付刚好满足需求的代码
- **"代码是负债"** — 每一行代码都需要维护、测试、理解，写得越少越好
- **Unix 哲学** — 做一件事，做好一件事

## 最佳实践

1. **不要跳过任何 Gate** — 即使看起来明显需要写代码，也过一遍
2. **诚实面对 Gate 2** — 找到已有方案比写新的节省大量时间
3. **Gate 7 的核心是"最小"** — 不是"写最好的代码"，而是"写刚好够用的代码"
4. **接受不完美** — 最小可行方案可能不够优雅，但够用即可
5. **留下检查痕迹** — 在代码注释或 commit message 中体现检查结果

## 示例

### 示例 1：用户要求加一个 URL 验证函数

```
## 最小可行决策检查

| # | Gate | 结果 | 说明 |
|---|------|------|------|
| 1 | Does this need to exist? | ✅ | 用户需要在表单中验证 URL |
| 2 | Already in this codebase? | ❌ | 搜索无现成验证逻辑 |
| 3 | stdlib does it? | ✅ | JavaScript 内置 `URL` 构造函数可用来验证 |
| 4 | Native platform feature? | ✅ | `<input type="url">` + 浏览器原生表单验证 |
| 5 | Installed dependency? | ✅ | 无需装额外包 |
| 6 | One line? | ✅ | `try { new URL(url) } catch { return false }` 一行搞定 |
| 7 | Only then: minimum | ❌ | 不需要写函数，直接在表单代码中使用 |

**结论：** 不需要写新函数，用原生 URL 构造函数或 HTML 输入类型即可
```

### 示例 2：用户要求写一个日期格式化工具

```
## 最小可行决策检查

| # | Gate | 结果 | 说明 |
|---|------|------|------|
| 1 | Does this need to exist? | ✅ | 需要在 UI 中展示格式化日期 |
| 2 | Already in this codebase? | ❌ | 项目中没有日期格式化工具 |
| 3 | stdlib does it? | ✅ | `Intl.DateTimeFormat` 可直接用 |
| 4 | Native platform feature? | ✅ | 浏览器/Node 都支持 |
| 5 | Installed dependency? | ✅ | 无需额外依赖 |
| 6 | One line? | ✅ | `new Intl.DateTimeFormat('zh-CN').format(date)` |
| 7 | Only then: minimum | ❌ | 不需要工具函数，直接内联使用 |

**结论：** 不需要写新工具函数，直接用 `Intl.DateTimeFormat`
```
