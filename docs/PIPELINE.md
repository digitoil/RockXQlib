# 流水线开发

画布（GUI 拖拽）是主入口；流水线层让它**可复用、可复现、可批量**，两者共用同一套校验与执行器。

## 在界面里（工作流菜单）
| 菜单 | 作用 |
|---|---|
| 从模板新建… | 载入 `pipelines/` 下的模板，可填参数覆盖，载入后继续拖拽修改 |
| 保存当前画布为模板… | 画布 → `pipelines/<名>.json`，下次直接复用 |
| AI 建模助手（对话） | 右侧对话面板：边聊边改画布、解释参数、运行后诊断/解读结果（见下） |
| 参数扫描… | 对当前画布按「节点id.属性=值1,值2」做网格，逐组合真实运行并存档，结束后自动还原被改的属性 |
| 运行记录… | 每次一键运行自动存档（画布+指标），Ctrl 多选可对比（指标表 + 参数差异 + 各指标最优），也可一键载回画布 |

## 命令行（批量 / CI / 服务器）
```
python -m pipeline nodes
python -m pipeline validate pipelines/lgb_alpha158.yaml
python -m pipeline run pipelines/lgb_alpha158.yaml --set universe=csi500
python -m pipeline run pipelines/lgb_alpha158.yaml --backend dry     # 无 Qt/qlib，只验接线与数据流
python -m pipeline sweep pipelines/lgb_alpha158.yaml --grid n4.model_class=LGBModel,XGBModel
python -m pipeline runs --compare latest <另一个run_id>
python -m pipeline export pipelines/lgb_alpha158.yaml out.json      # GUI「导入JSON」可用
python -m pipeline generate "CSI500 + LGB，2019 起回测" --model qwen3
python -m pipeline qrun workflows/lgb_close_minimal.yaml --provider-uri ./qlib_data
```

`qrun` 不走画布节点，而是 qlib 的 `task_train`（训练、recorder、配置里的回测）。说明见 [QLIB_RESEARCH.md](QLIB_RESEARCH.md)。

## 流水线文件
链式写法，同名端口自动连线；`${param}` 引用参数；dict 属性自动转 JSON 文本。
见 `pipelines/lgb_alpha158.yaml`。也可直接写 `nodes` / `links`（即画布导出的 JSON）。

## 运行记录 `runs/<时间>_<名>_<配置哈希>/`
`workflow.json`（实际执行的图）· `manifest.json`（状态/耗时/逐节点/git/哈希）· `metrics.json`（有才写，绝不伪造）· `run.log`。
配置哈希相同 ＝ 同一配置，便于判断两次结果能否对比。

## 设计约束
- `pipeline/` 只依赖标准库（YAML 可选），节点规格用 AST 静态提取，不导入 Qt/qlib
- 演练后端不产生任何行情/指标；LLM 产物必须过校验、先预览后落地
- 新增节点只需在节点类里声明端口/属性，规格、校验、LLM 说明书自动跟随

## 语义检查（`pipeline/lint.py`）
结构合法≠参数合理。流水线载入、AI 生成、参数扫描、一键运行前都会检查：
- 错误：JSON 属性解析失败、日期格式非法、起止颠倒、训练/验证/测试区间重叠或顺序颠倒（前视泄漏）
- 警告：回测区间超出测试区间、股票池与基准不匹配

## AI 建模助手（交互式）
对话 → 助手给出**提案**（文字 + 修改清单）→ 你点「应用到画布」（可「撤销上次应用」）→ 「应用并运行」→ 运行结束后点「诊断 / 解读上次运行」。
- 每轮都把**画布当前状态**和**上次运行的真实结果**发给 LLM，所以手动拖拽后继续聊也不会错位
- 助手只出提案；改画布、启动运行必须你点按钮。`run:true` 只是建议
- 提案必须过结构校验 + 语义检查（前视泄漏等），不过就让模型修，仍不行则不动画布并说明原因
- 失败原因来自节点真实输出（执行器会捕获节点打印的失败信息），指标只引用真实数字
- 接口走 OpenAI 兼容协议（Ollama / GPUStack / vLLM / OpenAI）；API Key 不落盘
