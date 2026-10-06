"""测试包。

⚠️ 这个 ``__init__.py`` 不是装饰，是**必需的**。

Python 的导入规则：**常规包（有 ``__init__.py``）优先于命名空间包
（无 ``__init__.py``）**，无论路径顺序如何。本目录原先没有 ``__init__.py``，
于是它只是一个"命名空间包候选"，而解释器会继续往后扫描 sys.path ——
只要后面任何一层存在名为 ``tests`` 的常规包，就会整个覆盖本目录。

本机就撞上了这种情况：site-packages 里的 ``_editable_impl_fracsim.pth``
把 ``D:\GitBase\FracStudio\FracSim`` 加进了 sys.path，那个项目有
``FracSim\tests\__init__.py``。结果：

    python -m unittest tests.test_pipeline
    -> ModuleNotFoundError: No module named 'tests.test_pipeline'

报错指向 ``tests`` 这个包名，而本项目的 ``tests/test_pipeline.py`` 明明存在，
极难定位。（同类问题此前在 ``core`` 和 ``nodes`` 上各踩过一次。）

补上本文件后，本目录成为常规包，位于 sys.path 靠前位置，遮蔽问题消失。

⚠️ 不要删除本文件。
"""
