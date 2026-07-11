# mock_external 外部公开信息模拟资料

这个目录用于放“外部公开信息检索”的可提交模拟资料。

它和 `live/` 的区别：

- `live/`：黑盒检索系统运行时写入，可能含内部真实数据，不提交真实内容。
- `mock_external/`：为了 Demo、E2E、评审说明而提交的公开信息模拟 fixture。

当前后端真实外部检索入口是 `code/backend/external_search.py`：

- 配置 `EXTERNAL_SEARCH_ENDPOINT` 时，会调用真实外部检索服务。
- 未配置时，会返回 `external-intel/gap`，要求报告把公开客户事实标为待核实。

E2E case 里使用 `public-demo://...` 来源来模拟外部公开信息；本目录保留同类样例，方便读仓库的人直接看到“外部检索模拟资料”的形态。
