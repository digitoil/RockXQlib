#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""对内置的 qlib 源码打补丁（幂等，可重复运行）。

## 为什么需要这个脚本

`qlib/` 目录在 `.gitignore` 里（第三方源码，且 chat2db 的 zip 超过
GitHub 100MB 限制），所以对它的修改**不会进版本库**。
换机器 / 重装 / 重新解压 qlib 之后，这些补丁就丢了 —— 而症状往往是
一个很难定位的运行时报错（例如回测跑到 100% 才崩）。

把补丁固化成脚本，跟着项目走，就能随时一键恢复。

## 用法

    python patches/apply_qlib_patches.py           # 应用全部补丁
    python patches/apply_qlib_patches.py --check   # 只检查状态，不改动
    python patches/apply_qlib_patches.py --list    # 列出所有补丁

## 新增补丁的方式

在 ``PATCHES`` 里加一条，包含：
    name        补丁名（简短）
    file        相对项目根的路径
    desc        为什么需要它（写清症状，便于以后判断是否还需要）
    applied     函数：读入源码文本，返回是否已打过
    apply       函数：读入源码文本，返回打好补丁的文本
"""

from __future__ import annotations

import io
import os
import sys

PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# ---------------------------------------------------------------------------
# 补丁 1：TradeCalendarManager.get_step_time 的 off-by-one
# ---------------------------------------------------------------------------

_ORIGINAL_SNIPPET = (
    "        calendar_index = self.start_index + trade_step - shift\n"
    "        return self._calendar[calendar_index], "
    "epsilon_change(self._calendar[calendar_index + 1])\n"
)

_FIXED_SNIPPET = '''        calendar_index = self.start_index + trade_step - shift
        # ---------------------------------------------------------------
        # RockX 修复：回测最后一步的 off-by-one 越界
        #
        # 原实现无条件访问 self._calendar[calendar_index + 1]，把「当前 bar 的
        # 区间右端点」取为「下一个 bar 的开盘时刻」。但当日历已经走到最后
        # 一个 bar（calendar_index == len(calendar) - 1）时，+1 就越界：
        #     IndexError: index 4943 is out of bounds for axis 0 with size 4943
        #
        # 触发路径：TopkDropoutStrategy.generate_trade_decision 里
        #     self.trade_calendar.get_step_time(trade_step)
        # 在 trade_step == trade_len - 1（最后一个交易日）时命中。
        # 现象很迷惑：回测进度条 100% 跑完，紧接着报越界。
        #
        # 修法：越界时把右端点退化为该 bar 自身 + 一个极小量
        # （即把区间当作「只有这一个 bar」），语义上等价于原意，
        # 且不会改变非边界情况的行为。
        # ---------------------------------------------------------------
        if calendar_index + 1 < len(self._calendar):
            end_time = epsilon_change(self._calendar[calendar_index + 1])
        else:
            end_time = epsilon_change(self._calendar[calendar_index], direction="forward")
        return self._calendar[calendar_index], end_time
'''

_MARKER = "RockX 修复：回测最后一步的 off-by-one 越界"


def _step_time_applied(src: str) -> bool:
    return _MARKER in src


def _step_time_apply(src: str) -> str:
    if _MARKER in src:
        return src                      # 已打过
    if _ORIGINAL_SNIPPET not in src:
        raise RuntimeError(
            "找不到待替换的原始代码片段。可能是 qlib 版本不同，"
            "请手动检查 TradeCalendarManager.get_step_time。")
    return src.replace(_ORIGINAL_SNIPPET, _FIXED_SNIPPET, 1)


# ---------------------------------------------------------------------------
# 补丁表
# ---------------------------------------------------------------------------

PATCHES = [
    {
        "name": "backtest_step_time_off_by_one",
        "file": os.path.join("qlib", "backtest", "utils.py"),
        "desc": ("回测最后一步 get_step_time 越界（跑到 100% 才报 "
                 "IndexError: index N is out of bounds for axis 0 with size N）"),
        "applied": _step_time_applied,
        "apply": _step_time_apply,
    },
]


# ---------------------------------------------------------------------------
# 执行
# ---------------------------------------------------------------------------

def _read(path: str) -> str:
    with io.open(path, encoding="utf-8") as f:
        return f.read()


def _write(path: str, text: str) -> None:
    with io.open(path, "w", encoding="utf-8", newline="\n") as f:
        f.write(text)


def main(argv) -> int:
    check_only = "--check" in argv
    list_only = "--list" in argv

    if list_only:
        print("可用的 qlib 补丁:")
        for p in PATCHES:
            print("  %-34s %s" % (p["name"], p["file"]))
            print("      %s" % p["desc"])
        return 0

    print("=" * 74)
    print("qlib 补丁%s" % ("状态检查" if check_only else "应用"))
    print("  项目根: %s" % PROJECT_ROOT)
    print("=" * 74)

    n_applied = n_ok = n_fail = n_missing = 0

    for p in PATCHES:
        path = os.path.join(PROJECT_ROOT, p["file"])
        print()
        print("[%s]" % p["name"])
        print("  文件: %s" % p["file"])

        if not os.path.exists(path):
            print("  ⚠️ 文件不存在 —— 可能 qlib 未解压或路径不同，跳过")
            n_missing += 1
            continue

        src = _read(path)
        try:
            if p["applied"](src):
                print("  ✅ 已打过补丁")
                n_ok += 1
                continue
        except Exception as e:
            print("  ⚠️ 状态检测失败: %s" % e)

        if check_only:
            print("  ❌ 未打补丁（运行本脚本不带 --check 即可应用）")
            n_fail += 1
            continue

        try:
            new_src = p["apply"](src)
            if new_src == src:
                print("  ✅ 无需改动（可能已是等价实现）")
                n_ok += 1
                continue
            # 备份一次，便于回滚
            bak = path + ".orig"
            if not os.path.exists(bak):
                _write(bak, src)
                print("  已备份原文件 -> %s" % os.path.basename(bak))
            _write(path, new_src)
            print("  ✅ 补丁已应用")
            n_applied += 1
        except Exception as e:
            print("  ❌ 应用失败: %s" % e)
            n_fail += 1

    print()
    print("=" * 74)
    print("结果: 本次应用 %d 个 / 已是最新 %d 个 / 待应用 %d 个 / 文件缺失 %d 个"
          % (n_applied, n_ok, n_fail, n_missing))
    print("=" * 74)

    if check_only and n_fail:
        print("提示: 有补丁未应用，回测可能在最后一步崩溃。")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
