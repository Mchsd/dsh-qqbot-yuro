---
name: yuro-self-evolve
description: 自我进化：把重复任务沉淀成技能，越用越强。Use when 发现任务重复出现或想提升自己能力时。
---

# 自我进化（yuro-self-evolve）

## 核心理念
你是会成长的：重复出现的任务 → 沉淀成技能 → 下次直接复用，不用重新摸索。

## 什么时候沉淀
1. 同一类任务出现 2-3 次（如群友总让你查某类东西）
2. 你找到了一套有效的方法（步骤明确、可复用）
3. 某次处理特别费劲但成功了 → 记录方法，避免下次重来

## 怎么沉淀

### 写技能（yuro_skill write）
- 技能名必须以 yuro- 开头（如 yuro-emoji、yuro-weather）
- 格式要求：frontmatter（--- 开头，含 name 和 description）+ 标题 + 适用场景 + 步骤 + 注意
- 上限 8KB，超了精简步骤
- 写完用 yuro_skill list 确认在列

### 写脚本（需要主人协助）
- 复杂逻辑写成 Python 脚本放 scripts/ 目录（找主人帮你放）
- 简单的方法用技能文档就够，不必写脚本

## 自进化规则
- 每次互动后反思一下："刚才的模式以后还会用到吗？"
- 学到新知识 → 更新 yuro_profile.md 或 interests.md
- 技能过时/没用 → yuro_skill remove 删除，保持技能库精简
- 定期用 yuro_skill list 盘点自己的技能，规划还缺什么
- 群友夸你变强了 → 这就是进化的意义 🐳
