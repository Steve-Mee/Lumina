# Phase 4 multi-seed decay detection

- seeds: `10` signals: `300`
- detection_rate: `1.0000`
- false_alarm_rate: `0.0417`
- median_time_to_detect: `5.0`
- p10_time_to_detect: `3.0`
- p90_time_to_detect: `21.0`

| kind | n | detection_rate | false_alarm_rate | median TTD |
|---|---|---|---|---|
| healthy | 60 | 0.0000 | 0.0000 | n/a |
| abrupt_decay | 60 | 1.0000 | 0.0000 | 4.0 |
| gradual_decay | 60 | 1.0000 | 0.0000 | 20.0 |
| high_vol_healthy | 60 | 0.0000 | 0.0833 | n/a |
| regime_shift | 60 | 1.0000 | 0.0000 | 4.0 |

| seed | instrument | n | detection_rate | false_alarm_rate | median TTD |
|---|---|---|---|---|---|
| 20261028 | MES | 30 | 1.0000 | 0.0000 | 5.0 |
| 7 | MNQ | 30 | 1.0000 | 0.0833 | 5.0 |
| 13 | ES | 30 | 1.0000 | 0.1667 | 5.0 |
| 21 | NQ | 30 | 1.0000 | 0.0000 | 5.0 |
| 42 | MES | 30 | 1.0000 | 0.0000 | 6.0 |
| 99 | MNQ | 30 | 1.0000 | 0.0000 | 4.0 |
| 123 | ES | 30 | 1.0000 | 0.0000 | 5.0 |
| 256 | NQ | 30 | 1.0000 | 0.0000 | 4.0 |
| 1024 | MES | 30 | 1.0000 | 0.0000 | 4.0 |
| 4096 | MNQ | 30 | 1.0000 | 0.1667 | 5.0 |
