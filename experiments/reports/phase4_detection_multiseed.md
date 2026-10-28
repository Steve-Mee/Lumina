# Phase 4 multi-seed decay detection

- seeds: `10` signals: `300`
- detection_rate: `1.0000`
- false_alarm_rate: `0.0333`
- median_time_to_detect: `6.0`
- p10_time_to_detect: `4.0`
- p90_time_to_detect: `12.0`
- max_time_to_detect: `13.0`

| kind | n | detection_rate | false_alarm_rate | median TTD | p90 TTD | max TTD |
|---|---|---|---|---|---|---|
| healthy | 60 | 0.0000 | 0.0000 | n/a | n/a | n/a |
| abrupt_decay | 60 | 1.0000 | 0.0000 | 5.0 | 6.0 | 7.0 |
| gradual_decay | 60 | 1.0000 | 0.0000 | 12.0 | 12.0 | 13.0 |
| high_vol_healthy | 60 | 0.0000 | 0.0667 | n/a | n/a | n/a |
| regime_shift | 60 | 1.0000 | 0.0000 | 6.0 | 8.0 | 9.0 |

| seed | instrument | n | detection_rate | false_alarm_rate | median TTD |
|---|---|---|---|---|---|
| 20261028 | MES | 30 | 1.0000 | 0.0000 | 6.0 |
| 7 | MNQ | 30 | 1.0000 | 0.0000 | 7.0 |
| 13 | ES | 30 | 1.0000 | 0.1667 | 6.0 |
| 21 | NQ | 30 | 1.0000 | 0.0000 | 6.0 |
| 42 | MES | 30 | 1.0000 | 0.0000 | 7.0 |
| 99 | MNQ | 30 | 1.0000 | 0.0000 | 6.0 |
| 123 | ES | 30 | 1.0000 | 0.0000 | 6.0 |
| 256 | NQ | 30 | 1.0000 | 0.0000 | 6.0 |
| 1024 | MES | 30 | 1.0000 | 0.0000 | 6.0 |
| 4096 | MNQ | 30 | 1.0000 | 0.1667 | 7.0 |
