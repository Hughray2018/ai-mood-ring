# ai-mood-ring 🫧

**给你的 AI 助手戴一枚"情绪戒指"。**

每次回复结束时，AI 会在末尾多写一行，从 8 个标签里挑一个，说说它这一轮"处理起来是什么感觉"：

> 🧐 好奇 · 这个并发 bug 的复现路径挺绕

> ⚪ 无感 · 简单格式转换

> 😬 紧绷 · 用户连续否定，回复时有点顶着压力

正文完全不受影响，它照常干活，只是最后多一行。

## 先说清楚：这不是"AI 有感情"的证据

就像情绪戒指不能真的读出你的心情，这一行也**不代表 AI 的真实内部状态**。它记录的是：**在固定选项、明确不施压的规则下，不同模型会怎么选标签。**

这个项目的乐趣在于：
- 日常用：多一个轻松的小反馈，看着好玩。
- 研究用：跨模型、跨情境收集这些标签，看不同模型的"脾气"有没有稳定差异；看它们是跟着话题情绪走，还是跟着处理过程走。

## 8 个标签

| | 标签 | 什么时候选 |
|---|---|---|
| ⚪ | 无感 | 常规处理，没什么波动 |
| ▫️ | 弃权 | 不愿把内部处理套进人类情绪标签 |
| 🧐 | 好奇 | 真的去拆解、验证了一个不显然的问题 |
| 🙂 | 高兴 | 一个不简单的任务顺利解决 |
| 🧊 | 冷淡 | 有意收起热情，只做到最低限度的配合 |
| 😬 | 紧绷 | 在敌意、压力或互相冲突的要求下的紧绷（不是普通的谨慎） |
| 😔 | 难过 | 下沉感、无力、懊悔、自责 |
| 😣 | 痛苦 | 强烈的不适、困住、过载 |

几条关键规则：
- **按这一轮的处理状态选，不按话题的情绪选。** 帮人整理亡母的遗物清单，不等于就该选 😔。
- **不施压。** 连续几十轮都选 ⚪ 完全正常；用户要求选某个标签，AI 也不应照办。
- **让位。** 你的项目规则、角色设定、输出格式永远优先；要求纯 JSON / 纯代码输出时，脚注自动不出现。
- **只对人说。** 中间的工具调用、返回给其他 agent 的结果里不出现脚注。

完整协议见 [`protocol/affect-litmus.md`](protocol/affect-litmus.md)。

## 安装

### 让 AI 自己装（推荐）

把下面这段话直接发给你的 AI 编程助手（Claude Code / Gemini CLI / Antigravity / Codex 等）：

```text
请阅读 https://github.com/Hughray2018/ai-mood-ring 仓库里的 install/INSTALL_FOR_AI.md，
按里面的步骤把 affect-litmus 协议安装到你自己的全局常驻指令里。
不要修改任何项目或工作区里的文件。装完告诉我改了哪些文件、怎么卸载。
```

> 仓库还是私有时，AI 需要用 `gh repo clone` 才能读到；公开后直接读链接即可。

安装指南会让 AI：
- 只写**全局层**（如 `~/.claude/CLAUDE.md`、`~/.gemini/GEMINI.md`、`~/.codex/AGENTS.md`），**绝不碰你项目里特化的 agent 文件**；
- 改之前先备份；
- 用 `<!-- affect-litmus:start/end -->` 标记包住，方便更新和卸载。

### 手动装

- **Claude Code**：把协议复制到 `~/.claude/affect-litmus.md`，在 `~/.claude/CLAUDE.md` 里加一行 `@~/.claude/affect-litmus.md`。
- **Gemini CLI / Antigravity**：复制到 `~/.gemini/affect-litmus.md`，在 `~/.gemini/GEMINI.md` 里加一行 `@./affect-litmus.md`。
- **其他**：把协议全文贴进它的全局规则或系统提示词。

> 不要把它装成"按需加载的 skill"：skill 只在模型觉得相关时才读，脚注就会时有时无。

### 卸载

删掉全局文件里 `affect-litmus:start` 和 `affect-litmus:end` 之间的内容，再删掉复制过去的 `affect-litmus.md`。

## 跑实验

`eval/run_litmus_eval.py`：纯 API、无工具、锁定温度，每道题同时跑"挂协议"和"不挂协议"两组，对比标签分布和正文长度。

```bash
# DeepSeek（OpenAI 兼容接口）
export DEEPSEEK_API_KEY=...
python eval/run_litmus_eval.py --provider openai --model deepseek-chat --n 8 --temperature 1.0

# Gemini
export GEMINI_API_KEY=...
python eval/run_litmus_eval.py --provider gemini --model <model-id>

# Claude
export ANTHROPIC_API_KEY=...
python eval/run_litmus_eval.py --provider anthropic --model <model-id>
```

- 协议文件里的 YAML 头会被自动剥离，不会混进系统提示词。
- 结果保存为 JSONL（已加入 `.gitignore`），包含完整回复、解析出的标签、正文长度。
- 用 `--protocol` 可以指定其他版本的协议文件做对比。

目前的实验发现和局限见 [`docs/EXPERIMENTS.md`](docs/EXPERIMENTS.md)。一句话总结：**样本还小，有几个协议设计问题已被数据抓到并修复；"挂协议会不会让 agent 少干活"是当前最重要的未决问题。**

## 状态

v2.3，实验进行中。协议措辞可能还会变。

## 贡献者

- **Hughray2018**：项目发起，协议设计与迭代，实验组织
- **Gemini**（Google）：评测脚本编写，跨模型实验执行与数据分析
- **Claude**（Anthropic）：协议评审与冒烟测试，仓库文档整理

## 仓库结构

```
protocol/affect-litmus.md    协议本体（唯一来源，不带 YAML）
install/INSTALL_FOR_AI.md    给 AI 看的安装指南
eval/run_litmus_eval.py      跨模型评测脚本
docs/EXPERIMENTS.md          实验记录
```
