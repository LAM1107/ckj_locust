# 单接口发压上限探测

目标：先测清楚当前“一台 master + 一台 worker”拓扑下，`single_list_lite` 的稳定上限。

## 适用范围

- 场景：`single_list_lite`
- 目标：测发压机上限，不混入支付链路
- 机器：1 台 master，1 台 worker

## 先决条件

1. worker 机使用最新 `run_distributed_v2.ps1`
2. worker 机有足够 token 文件
3. 两台机器时间同步，网络互通

## 建议先从 2 个 worker 进程开始

不要一上来就开很多 worker。先用 `2`，稳定后再试 `3`。

### worker 机启动

```powershell
cd D:\project\gacha_performance_test
.\run_distributed_v2.ps1 `
  -Mode worker `
  -Headless `
  -MasterHost <MASTER_IP> `
  -WorkerCount 2 `
  -WorkerIndexOffset 0 `
  -TotalWorkerCount 2 `
  -ScenarioMode single_list_lite `
  -TokenFile D:\secret\user_token.txt
```

### master 机压测矩阵

按下面顺序一组一组跑：

1. `u200 r5`
2. `u300 r5`
3. `u300 r10`
4. `u400 r10`
5. `u500 r10`

每组先跑 `2m`，稳定后再延长到 `5m`。

```powershell
cd D:\project\gacha_performance_test
.\run_distributed_v2.ps1 `
  -Mode master `
  -Headless `
  -Users 200 `
  -SpawnRate 5 `
  -RunTime 2m `
  -ResetStats `
  -OnlySummary `
  -ScenarioMode single_list_lite `
  -TotalWorkerCount 2 `
  -CsvPrefix result\probe_u200_r5 `
  -HtmlReport result\probe_u200_r5.html
```

把 `Users`、`SpawnRate`、输出文件名前缀替换成每一组对应值即可。

## 什么时候算稳定

同时满足下面几条，才算这一档可用：

1. master 日志没有持续出现 `Discarded report from unrecognized worker`
2. 没有 `The last worker went missing`
3. worker 没有频繁 `failed to send heartbeat`
4. worker CPU 不长期高于 `85%`
5. 错误率可接受

## 如果 2 个 worker 稳了，再试 3 个

### worker 机

```powershell
cd D:\project\gacha_performance_test
.\run_distributed_v2.ps1 `
  -Mode worker `
  -Headless `
  -MasterHost <MASTER_IP> `
  -WorkerCount 3 `
  -WorkerIndexOffset 0 `
  -TotalWorkerCount 3 `
  -ScenarioMode single_list_lite `
  -TokenFile D:\secret\user_token.txt
```

### master 机

把 `-TotalWorkerCount` 改成 `3`，再重复上面的矩阵。

## 结果判断

- 如果 `2 worker` 稳、`3 worker` 开始频繁掉 heartbeat：说明瓶颈在发压机 CPU
- 如果 `u300` 就不稳：先看 token、网络、旧进程残留
- 如果 `u500` 不稳但 `u400` 稳：把 `u400` 作为当前拓扑的可信上限

## 建议

- 先找“稳定上限”，再追“极限上限”
- 单接口压测不要混支付链路
- 如果目标是稳定 `u500+`，优先考虑增加 worker 机，而不是继续硬堆单机 worker 进程数
