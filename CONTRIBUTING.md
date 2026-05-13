# 贡献指南

感谢你愿意为 ticket-sniper 贡献代码！请在提交 PR 之前仔细阅读以下指南。

---

## 如何贡献

### 报告问题

- 提交 Issue 前请先搜索是否已有相同问题
- Bug 报告请包含以下信息：
  - Python 版本、操作系统环境
  - 完整的错误信息（Traceback）
  - 复现步骤
  - `config.yaml` 中对应的配置（非敏感部分）

### 功能提议

- 新的抢票平台支持
- 性能优化
- 代码质量改进
- 文档完善

请先开一个 Issue 讨论，确认方向后再提交 PR。

---

## 开发环境

### 环境要求

- Python 3.10+
- Git
- ADB（用于 ADB 相关功能测试）

### 本地开发

```bash
# 1. Fork 本仓库并克隆
git clone https://github.com/TsungShr/ticket-sniper.git
cd ticket-sniper

# 2. 创建虚拟环境
python -m venv venv
# macOS / Linux
source venv/bin/activate
# Windows
.\venv\Scripts\activate

# 3. 安装依赖（包含开发依赖）
pip install -r requirements.txt

# 4. 创建本地分支
git checkout -b feat/your-feature-name
```

### 代码规范

本项目遵循以下规范：

| 规则 | 说明 |
|------|------|
| **类型提示** | 所有新增代码必须添加完整的类型注解（参考 `platforms/base.py`） |
| **docstring** | 公开函数 / 类需要中文 docstring，说明参数和返回值 |
| **行长度** | 不超过 120 字符 |
| **异步函数** | 优先使用 `async/await`，避免混用同步和异步代码 |
| **错误处理** | 网络请求需捕获 `aiohttp.ClientError`，不要裸抛异常 |
| **日志** | 使用 `logging.getLogger(__name__)`，不要用 `print` 调试 |

### 运行测试

```bash
pytest tests/ -v
```

确保所有测试通过后再提交 PR。

---

## 分支命名

| 前缀 | 用途 | 示例 |
|------|------|------|
| `feat/` | 新功能 | `feat/add-ticketone-platform` |
| `fix/` | Bug 修复 | `fix/maoyan-blind-mode-timeout` |
| `perf/` | 性能优化 | `perf/adb-connection-pool` |
| `refactor/` | 代码重构 | `refactor/extract-ntp-module` |
| `docs/` | 文档更新 | `docs/improve-contributing-guide` |
| `test/` | 测试相关 | `test/add-integration-tests` |

---

## 提交规范

提交信息格式：

```
<类型>(<范围>): <简短描述>

[可选的详细说明]
```

示例：

```
feat(pxq): 添加 refresh_token 自动续期逻辑

在抢票过程中自动刷新即将过期的 access_token，
避免因 token 过期导致请求失败。

Closes #12
```

类型可选值：`feat`、`fix`、`perf`、`refactor`、`docs`、`test`、`chore`

---

## PR 规范

1. PR 标题清晰描述改动内容
2. PR 描述包含：
   - 改动的目的和背景
   - 主要改动点
   - 是否有需要 Reviewer 重点关注的地方
3. 一个 PR 只做一件事
4. 保持提交历史整洁，必要时做 `git rebase`
5. 确保 CI（如果有）全部通过

---

## 新增平台

如果要为新平台添加支持，请：

1. 在 `platforms/` 下创建 `新平台名.py`，继承 `PlatformGrabber` 抽象基类
2. 实现 `name`、`warmup()`、`grab()` 三个成员
3. 在 `main.py` 的 `grabbers` 列表中添加实例化逻辑
4. 在 `config.yaml.example` 中添加对应的配置示例
5. 在 `tests/` 下添加单元测试

参考现有实现：`platforms/piaoxingqiu.py`（HTTP API 型）和 `platforms/damai.py`（ADB 坐标型）。

---

## 敏感信息处理

**请勿在 PR 中提交任何真实凭据或个人信息：**

- Token、API Key、refresh_token 等
- 手机号、真实姓名
- 设备 ID 等可能用于追踪的信息

`config.yaml` 已在 `.gitignore` 中忽略，但请在提交前仔细检查。

---

## 行为准则

- 保持礼貌和尊重
- 技术讨论聚焦于代码和方案
- 欢迎提出不同意见，但要以理服人

---

有问题欢迎提 Issue 或讨论。
