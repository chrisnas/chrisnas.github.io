# Medium Posts Migration Summary

Generated on: 2026-05-09 13:54:21

## Overview

Source: 3 Medium ETW/TraceEvent posts saved as HTML
- Posts migrated: 3
- Total links checked: 34
- Alive: 7
- Redirected: 16
- Dead: 7
- Replaced (cross-post): 4

## Migrated Posts

| # | Title | Date | Path | Images | Links | Dead |
|---|-------|------|------|--------|-------|------|
| 1 | Replace .NET performance counters by CLR event tracing | 2018-06-19 | /posts/2018-06-19_replace-net-performance-counters/ | 7 | 12 | 3 |
| 2 | Grab ETW Session, Providers and Events | 2018-07-26 | /posts/2018-07-26_grab-etw-session-providers/ | 7 | 12 | 3 |
| 3 | Monitor Finalizers, contention and threads in your application | 2018-09-28 | /posts/2018-09-28_monitor-finalizers-contention-threads/ | 2 | 10 | 1 |

## Per-Post Link Reports

### Replace .NET performance counters by CLR event tracing

| Status | URL | Link Text | Details |
|--------|-----|-----------|---------|
| ALIVE | https://github.com/dotnet/coreclr/blob/release/1.0.0/src/vm/threads.cpp | early versions of the Core CLR | 200 |
| ALIVE | http://download.microsoft.com/download/3/A/7/3A7FA450-1F33-41F7-9E6D-3AA95B5A6AE | a 2007 MSDN Magazine article | 200 |
| DEAD | https://www.microsoft.com/en-us/download/details.aspx?id=28567&WT.mc_id=DT-MVP-5 | the Perfview tool | 404; Wayback: https://web.archive.org/web/*/https://www.microsoft.com/en-us/download/details.aspx?id=28567&WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/windows-hardware/test/wpt?WT.mc_id=DT-MVP-50033 | Windows Performance Toolkit/xperf | -> https://learn.microsoft.com/en-us/windows-hardware/test/wpt?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/clr-etw-events?WT. | list of documented CLR events | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/clr-etw-events?WT.mc_id=DT-MVP-5003325 |
| ALIVE | https://github.com/dotnet/coreclr/tree/master/src | .NET Core source code | 200 |
| ALIVE | https://github.com/dotnet/coreclr/blob/master/src/vm/ClrEtwAll.man | exact payload schema | 200 |
| ALIVE | https://github.com/dotnet/coreclr/blob/master/src/vm/eventtrace.cpp | ETW::-prefixed methods and enums | 200 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/garbage-collection | AllocationTick event | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/garbage-collection-etw-events#gcallocationtick_v2_event?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/controlling-loggin | the tooling available | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/controlling-logging?WT.mc_id=DT-MVP-5003325 |
| DEAD | https://www.nuget.org/packages/Microsoft.Diagnostics.Tracing.TraceEvent/ | theMicrosoft.Diagnostics.Tracing.TraceEv | 404; Wayback: https://web.archive.org/web/*/https://www.nuget.org/packages/Microsoft.Diagnostics.Tracing.TraceEvent/ |
| DEAD | https://twitter.com/kookiz | Kevin Gosse | 403; Wayback: https://web.archive.org/web/*/https://twitter.com/kookiz |

### Grab ETW Session, Providers and Events

| Status | URL | Link Text | Details |
|--------|-----|-----------|---------|
| REPLACED | http://labs.criteo.com/2018/06/replace-net-performance-counters-by-clr-event-tra | Replace .NET performance counters by CLR | -> /posts/2018-06-19_replace-net-performance-counters/ |
| DEAD | https://www.nuget.org/packages/Microsoft.Diagnostics.Tracing.TraceEvent | Microsoft.Diagnostics.Tracing.TraceEvent | 404; Wayback: https://web.archive.org/web/*/https://www.nuget.org/packages/Microsoft.Diagnostics.Tracing.TraceEvent |
| DEAD | https://www.nuget.org/packages/Microsoft.Diagnostics.Tracing.TraceEvent.Samples/ | Microsoft.Diagnostics.Tracing.TraceEvent | 404; Wayback: https://web.archive.org/web/*/https://www.nuget.org/packages/Microsoft.Diagnostics.Tracing.TraceEvent.Samples/ |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/clr-etw-providers? | https://docs.microsoft.com/en-us/dotnet/ | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/clr-etw-providers?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/clr-etw-keywords-a | verbosity level | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/clr-etw-keywords-and-levels#etw-event-levels |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/clr-etw-keywords-a | the categories of events you want to rec | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/clr-etw-keywords-and-levels?WT.mc_id=DT-MVP-5003325 |
| ALIVE | https://github.com/Microsoft/perfview/blob/master/src/TraceEvent | open sourced | 200 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/clr-etw-keywords-a | Microsoft documentation | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/clr-etw-keywords-and-levels?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/clr-etw-keywords-a | Keyword | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/clr-etw-keywords-and-levels?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/clr-etw-events?WT. | the Microsoft documentation | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/clr-etw-events?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/exception-thrown-v | documents theExceptionThrown_V1 | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/exception-thrown-v1-etw-event?WT.mc_id=DT-MVP-5003325 |
| DEAD | https://twitter.com/kookiz | Kevin Gosse | 403; Wayback: https://web.archive.org/web/*/https://twitter.com/kookiz |

### Monitor Finalizers, contention and threads in your application

| Status | URL | Link Text | Details |
|--------|-----|-----------|---------|
| REPLACED | http://labs.criteo.com/2018/06/replace-net-performance-counters-by-clr-event-tra | Replace .NET performance counters by CLR | -> /posts/2018-06-19_replace-net-performance-counters/ |
| REPLACED | http://labs.criteo.com/2018/07/grab-etw-session-providers-and-events/ | Grab ETW Session, Providers and Events | -> /posts/2018-07-26_grab-etw-session-providers/ |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/standard/garbage-collection/implementing | Microsoft documentation aroundIDisposabl | -> https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/implementing-dispose?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/contention-etw-eve | the corresponding documentation explains | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/contention-etw-events?WT.mc_id=DT-MVP-5003325 |
| REPLACED | http://labs.criteo.com/2018/06/replace-net-performance-counters-by-clr-event-tra | a previous post | -> /posts/2018-06-19_replace-net-performance-counters/ |
| ALIVE | https://stackoverflow.com/questions/268680/how-can-i-monitor-the-thread-count-of | on stackoverflow | 200 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/standard/garbage-collection/app-domain-r | other ways described by the documentatio | -> https://learn.microsoft.com/en-us/dotnet/standard/garbage-collection/app-domain-resource-monitoring?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/thread-pool-etw-ev | many ETW events | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/thread-pool-etw-events?WT.mc_id=DT-MVP-5003325 |
| REDIRECT | https://docs.microsoft.com/en-us/dotnet/framework/performance/thread-pool-etw-ev | ThreadPoolWorkerThreadAdjustementAdjustm | -> https://learn.microsoft.com/en-us/dotnet/framework/performance/thread-pool-etw-events#threadpoolworkerthreadadjustmentadjustment?WT.mc_id=DT-MVP-5003325 |
| DEAD | https://twitter.com/kookiz | Kevin Gosse | 403; Wayback: https://web.archive.org/web/*/https://twitter.com/kookiz |

## Existing Posts Updated (Medium URLs -> Internal Paths)

| Post | URLs Replaced |
|------|--------------|
| content\posts\2018-11-13_get-process-name-challenge\index.md | 1 |
| content\posts\2018-12-06_in-process-clr-event\index.md | 2 |
| content\posts\2018-12-15_spying-on-net-garbage\index.md | 4 |
| content\posts\2019-02-12_building-your-own-java\index.md | 3 |
| content\posts\2019-02-22_debugging-friday-hunting-down\index.md | 2 |
| content\posts\2019-04-04_let-debug-the-core\index.md | 3 |
| content\posts\2019-05-28_spying-on-net-garbage\index.md | 2 |
| content\posts\2019-07-23_net-core-counters-internals\index.md | 4 |
| content\posts\2019-10-17_how-to-expose-your\index.md | 3 |
| content\posts\2020-04-18_build-your-own-net\index.md | 1 |
| content\posts\2020-12-08_build-your-own-net\index.md | 1 |
| content\posts\2022-07-28_digging-into-the-clr\index.md | 1 |
| content\posts\2022-10-23_clr-events-go-for\index.md | 1 |
| content\posts\2025-01-13_measuring-the-impact-of\index.md | 1 |

## Notes

- All 3 posts are co-authored with Kevin Gosse.
- Tags were manually assigned (not available in Medium metadata).
- Dates come from the 'Originally published at' footer (original Criteo Labs dates),
  not from Medium's article:published_time (which reflects the Medium republication date).
- Giscus comments will be enabled on these posts. GitHub Discussion
  threads will be created on first visitor interaction.
