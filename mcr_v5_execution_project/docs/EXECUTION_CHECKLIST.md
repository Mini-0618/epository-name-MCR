# MCR v5.0 执行清单

## Phase 0：安全边界
- [ ] 确认当前是本地测试工程
- [ ] 不访问外部网络
- [ ] 不执行危险 shell 命令
- [ ] 不删除用户文件
- [ ] 所有运行日志写入 `runtime_logs/`

## Phase 1：生成工程
- [ ] 运行 `python make_mcr_v5_execution_project.py`
- [ ] 进入 `mcr_v5_execution_project/`
- [ ] 确认存在 `src/mcr_v5/unified_loop.py`
- [ ] 确认存在 `config/mcr_v5.json`
- [ ] 确认存在 `docs/EXECUTION_CHECKLIST.md`

## Phase 2：最小运行
- [ ] 执行 `python run.py`
- [ ] 看到 `status: ok`
- [ ] 看到 `steps: 15`
- [ ] 看到 `events` 大于等于 15

## Phase 3：健康检查
- [ ] 执行 `python -m mcr_v5.health_check`
- [ ] 输出 `health_check: PASS`
- [ ] 无异常堆栈

## Phase 4：测试
- [ ] 执行 `python -m pytest`
- [ ] `test_unified_loop_runs_15_steps` 通过
- [ ] 如果 pytest 不存在，先只运行 health_check，不要重装环境

## Phase 5：15步循环验收
- [ ] Step 1  环境扫描
- [ ] Step 2  世界模型
- [ ] Step 3  机会检测
- [ ] Step 4  目标生成
- [ ] Step 5  任务执行
- [ ] Step 6  溯源记录
- [ ] Step 7  失败分析
- [ ] Step 8  模式检测
- [ ] Step 9  免疫巡逻
- [ ] Step 10 自修复
- [ ] Step 11 认知反思
- [ ] Step 12 全局广播
- [ ] Step 13 稳态调节
- [ ] Step 14 技能进化
- [ ] Step 15 Sleep 巩固

## Phase 6：产物检查
- [ ] `runtime_logs/provenance.jsonl` 已生成
- [ ] `runtime_logs/skills.jsonl` 已生成
- [ ] `runtime_logs/sleep_memory.jsonl` 已生成

## Phase 7：下一步扩展
- [ ] 把 `TaskEngine.execute()` 接入真实任务系统
- [ ] 把 `FailureAnalyzer` 接入真实 eval 结果
- [ ] 把 `EvolutionEngine` 接入 prompt 进化系统
- [ ] 把 `Homeostasis` 接入 token / CPU / memory 监控
- [ ] 把 `SleepConsolidator` 接入长期记忆库

## 当前结论

这是 MCR v5.0 的可执行骨架，不是最终完整系统。

验收标准：
- python run.py 能跑
- health_check PASS
- 15 个 step 全部出现
- runtime_logs 有记录
