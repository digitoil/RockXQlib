# Qlib 研究实验

画布节点适合把数据、模型、策略接在一起看。要复现一次 qlib 实验（初始化、训练、把预测和指标留在 recorder 里、再回测），用同一套 qlib API 的无界面入口。

## 跑什么

```bash
python -m pipeline qrun workflows/lgb_close_minimal.yaml --provider-uri ./qlib_data
python -m pipeline qrun workflows/lgb_alpha158.yaml
```

`qrun` 做的事和 `qrun` / `qlib.model.trainer.task_train` 相同：

1. `qlib.init`（数据目录必须已经是 qlib 的 bin 布局）
2. 按 `task.model` / `task.dataset` 构建模型与 `DatasetH`（或配置里写的其它 Dataset）
3. `model.fit`，并用 `R` 把参数、训练指标、`params.pkl`、`dataset` 写入 recorder
4. 执行 `task.record`：`SignalRecord` 写 `pred.pkl`，`SigAnaRecord` 写 IC，`PortAnaRecord` 用预测做回测

成功时，记录目录里有 `summary.json`。里面的行数和指标是从 recorder **重新读出来**的。预测加载失败、数据目录不存在、或 qlib 没装上，命令以非 0 退出，不写 `status: success`。

mlflow 不可用时，记录落在 `--uri-folder`（默认 `./mlruns`）下的本地文件里，不依赖 `MlflowClient`。配置里若自己写了 `qlib_init.exp_manager`，则用你指定的后端。

## 最小数据（不需要官方 cn_data）

`workflows/lgb_close_minimal.yaml` 只用收盘价特征（`DataHandlerLP` + `QlibDataLoader`），股票池名是 `pool`，回测基准是 `SH000300`。把 CSV 收成 qlib 目录：

```bash
python -m pipeline data-import prices.csv --out ./qlib_data --instrument-list pool
python -m pipeline qrun workflows/lgb_close_minimal.yaml --provider-uri ./qlib_data
```

CSV 需要日期、代码、开高低收、成交量。代码可以是 `600000.SH` 这种写法，导入时会收成 `SH600000`。基准 `SH000300` 也要在同一份数据里，否则回测会报基准不存在。配置里的训练 / 验证 / 测试 / 回测日期必须落在这份日历上。

自动化测试 `tests/test_qlib_research.py` 用约三个月、5 只股票加沪深 300 的随机行情走完这条链路，并检查 `pred.pkl` 能被另一个实验管理器重新打开，且回测产物 `report_normal_*.pkl` 在 recorder 里。

## 官方 Alpha158

`workflows/lgb_alpha158.yaml` 使用 `Alpha158`、CSI300、2008-01-01 至 2020-08-01。需要官方日频数据：

```bash
python -m qlib.cli.data qlib_data --target_dir ~/.qlib/qlib_data/cn_data --region cn
python -m pipeline qrun workflows/lgb_alpha158.yaml
```

仓库根目录的 `workflow_config_lstm_Alpha158*.yaml` 也是 qlib workflow，可以用同一条命令跑，但模型是 `pytorch_lstm_ts`，需要 PyTorch，并且同样依赖上面的 cn_data。没有数据时会失败，不会改用模拟训练。

## 和画布的关系

画布上的「Qlib 模型」节点仍然调用 `model.fit` / `model.predict`。没有预测时节点返回失败，工作流不会被记成成功。实验管理节点只记录上游真正传来的 `metrics`，不再写入固定的 accuracy / F1。

`pipelines/*.yaml` 仍是节点图模板。`workflows/*.yaml` 是 qlib 实验配置。两边都调用 qlib，但不要把节点图 YAML 交给 `qrun`。

## 还没做的

- 节点图一键运行还没有改成调用 `task_train`（交互式节点继续自己 `fit` / `predict`，回测仍走 `qlib.backtest.backtest`）。
- 根目录 LSTM 配置没有在无 GPU、无 cn_data 的环境里跑通；入口已经接上，缺依赖时会报错。
- 官方 `examples/benchmarks` 若在本机，仍用 `python -m pipeline import-benchmarks` 转成节点图模板，那是另一条入口。
