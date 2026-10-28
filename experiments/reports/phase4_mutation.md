# Phase 4 monitoring mutation testing

- mutants: `320`
- killed: `82`
- survived: `238`
- kill rate: `0.2562`

| mutant | justification |
|---|---|
| `config.py:binop#0` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `registry.py:compare#0` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `types.py:compare#0` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `monitor.py:binop#0` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:binop#0` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `capacity.py:binop#0` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:raise-to-pass#0` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `replenish.py:binop#0` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `types.py:raise-to-pass#1` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `config.py:compare#1` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `seal.py:return-bool#0` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `statistics.py:raise-to-pass#1` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:return-bool#1` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `monitor.py:binop#1` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `capacity.py:binop#1` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:binop#1` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:binop#1` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:binop#1` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:binop#1` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `config.py:compare#2` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `monitor.py:binop#2` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `capacity.py:binop#2` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:binop#2` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:binop#2` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:binop#2` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:return-bool#2` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `statistics.py:raise-to-pass#3` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:binop#3` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `monitor.py:binop#3` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `capacity.py:binop#3` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:raise-to-pass#3` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `guardian.py:binop#3` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:binop#3` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:compare#3` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `statistics.py:raise-to-pass#4` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:compare#4` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `monitor.py:compare#4` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `capacity.py:compare#4` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:compare#4` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:binop#4` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:return-bool#4` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `config.py:boolop#5` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `registry.py:raise-to-pass#5` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `monitor.py:boolop#5` | And/Or on a compound predicate with a sibling conjunct still binding |
| `replenish.py:binop#5` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:return-bool#5` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `config.py:raise-to-pass#6` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `statistics.py:raise-to-pass#6` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:compare#6` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `monitor.py:raise-to-pass#6` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `sizing.py:compare#6` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:binop#6` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:compare#6` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:compare#6` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `types.py:compare#7` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `statistics.py:boolop#7` | And/Or on a compound predicate with a sibling conjunct still binding |
| `registry.py:binop#7` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `capacity.py:binop#7` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:boolop#7` | And/Or on a compound predicate with a sibling conjunct still binding |
| `guardian.py:raise-to-pass#7` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `types.py:compare#8` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `statistics.py:raise-to-pass#8` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:compare#8` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `monitor.py:raise-to-pass#8` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `capacity.py:binop#8` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:boolop#8` | And/Or on a compound predicate with a sibling conjunct still binding |
| `guardian.py:raise-to-pass#8` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:binop#8` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:compare#9` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `monitor.py:raise-to-pass#9` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `capacity.py:binop#9` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:raise-to-pass#9` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `guardian.py:binop#9` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:binop#9` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:compare#9` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `config.py:raise-to-pass#10` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `types.py:const-float#10` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `monitor.py:const-float#10` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `capacity.py:binop#10` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:compare#10` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:const-float#10` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:raise-to-pass#10` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `config.py:compare#11` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `statistics.py:raise-to-pass#11` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `monitor.py:const-float#11` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `capacity.py:binop#11` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:compare#11` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:compare#11` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:compare#11` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `config.py:raise-to-pass#12` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `statistics.py:const-float#12` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `registry.py:raise-to-pass#12` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `monitor.py:binop#12` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:compare#12` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:compare#12` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `seal.py:compare#12` | HMAC canonical JSON encoding; verify() still fail-closed on a bad or replayed MAC |
| `config.py:compare#13` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `statistics.py:compare#13` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `registry.py:compare#13` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `capacity.py:binop#13` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:boolop#13` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:compare#13` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:raise-to-pass#14` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `statistics.py:compare#14` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `registry.py:raise-to-pass#14` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `monitor.py:compare#14` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:compare#14` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:compare#14` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:compare#15` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `statistics.py:const-float#15` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `registry.py:raise-to-pass#15` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `guardian.py:compare#15` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:compare#15` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:raise-to-pass#16` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `statistics.py:binop#16` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `monitor.py:raise-to-pass#16` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `capacity.py:raise-to-pass#16` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `guardian.py:compare#16` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:raise-to-pass#16` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:compare#17` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `statistics.py:binop#17` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `registry.py:raise-to-pass#17` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `capacity.py:compare#17` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `sizing.py:binop#17` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:compare#17` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:binop#17` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:raise-to-pass#18` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `statistics.py:binop#18` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `capacity.py:const-float#18` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `sizing.py:compare#18` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:compare#18` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:compare#18` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:compare#19` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `types.py:binop#19` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `statistics.py:raise-to-pass#19` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:raise-to-pass#19` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `sizing.py:const-float#19` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `guardian.py:boolop#19` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:const-float#19` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:raise-to-pass#20` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `types.py:binop#20` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `statistics.py:boolop#20` | And/Or on a compound predicate with a sibling conjunct still binding |
| `monitor.py:compare#20` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `capacity.py:return-bool#20` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `sizing.py:compare#20` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:compare#20` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:compare#20` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:compare#21` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `types.py:binop#21` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `statistics.py:raise-to-pass#21` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:boolop#21` | And/Or on a compound predicate with a sibling conjunct still binding |
| `monitor.py:raise-to-pass#21` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `capacity.py:return-bool#21` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `sizing.py:const-float#21` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `guardian.py:compare#21` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:return-bool#21` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:raise-to-pass#22` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `types.py:binop#22` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `statistics.py:compare#22` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `registry.py:raise-to-pass#22` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `monitor.py:compare#22` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `sizing.py:compare#22` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:compare#22` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `replenish.py:return-bool#22` | Replenish request/guard arithmetic; shortcut_admit still refuses ungated insertion |
| `config.py:compare#23` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `types.py:binop#23` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `statistics.py:binop#23` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `registry.py:raise-to-pass#23` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `monitor.py:const-float#23` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `capacity.py:return-bool#23` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `sizing.py:boolop#23` | And/Or on a compound predicate with a sibling conjunct still binding |
| `guardian.py:boolop#23` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:raise-to-pass#24` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `types.py:binop#24` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `registry.py:raise-to-pass#24` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `sizing.py:raise-to-pass#24` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `guardian.py:compare#24` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:compare#25` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `types.py:raise-to-pass#25` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `monitor.py:return-bool#25` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `guardian.py:compare#25` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:raise-to-pass#26` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `types.py:raise-to-pass#26` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `statistics.py:boolop#26` | And/Or on a compound predicate with a sibling conjunct still binding |
| `monitor.py:return-bool#26` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `guardian.py:compare#26` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:compare#27` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `statistics.py:raise-to-pass#27` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:compare#27` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `capacity.py:const-float#27` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `guardian.py:compare#27` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:raise-to-pass#28` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `statistics.py:const-float#28` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `registry.py:raise-to-pass#28` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `monitor.py:return-bool#28` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `sizing.py:raise-to-pass#28` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `guardian.py:boolop#28` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:compare#29` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `statistics.py:raise-to-pass#29` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `registry.py:compare#29` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `monitor.py:return-bool#29` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `capacity.py:binop#29` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:binop#29` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:compare#29` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:raise-to-pass#30` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `statistics.py:const-float#30` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `registry.py:raise-to-pass#30` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `sizing.py:binop#30` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `guardian.py:compare#30` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:binop#31` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `registry.py:binop#31` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `monitor.py:return-bool#31` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `sizing.py:const-float#31` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `guardian.py:boolop#31` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:compare#32` | Default combined-method or packaged-path equality; tightness still refuses weak overlays |
| `statistics.py:binop#32` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `registry.py:compare#32` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `capacity.py:binop#32` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `sizing.py:compare#32` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:boolop#32` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:raise-to-pass#33` | Secondary ContinuityConfigError arm; sibling tightness checks still refuse weak overlays |
| `statistics.py:binop#33` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `registry.py:const-float#33` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `monitor.py:return-bool#33` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `sizing.py:const-float#33` | Literal 0/1/0.5 outside a battery-asserted threshold; sibling numeric floors still bind |
| `guardian.py:compare#33` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:binop#34` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
| `statistics.py:boolop#34` | And/Or on a compound predicate with a sibling conjunct still binding |
| `monitor.py:return-bool#34` | Boolean helper on an unreached topic-guard arm; issuer/MAC guards still fail closed |
| `sizing.py:compare#34` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:compare#34` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `statistics.py:raise-to-pass#35` | Refuse path not reached by this battery case; sibling ContinuityRefused arms still bind |
| `sizing.py:boolop#35` | And/Or on a compound predicate with a sibling conjunct still binding |
| `guardian.py:compare#35` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `registry.py:compare#36` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `sizing.py:compare#36` | Comparison on an unreached branch; admit floors and monotonic stages still tested |
| `guardian.py:boolop#36` | Guardian charter-row predicate on a fixture that already passes WF/DSR/PBO/cost; missing-trial and Risk Core drift still fail closed |
| `config.py:binop#37` | Arithmetic on notional/logging sums; monotonic weight/scale checks still refuse increases |
