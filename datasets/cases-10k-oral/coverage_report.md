# 口语化版 A2UI Query 数据生产覆盖度报告

- **最终条数**: 5000
- **原始产出**: 7495
- **精确去重移除**: 0
- **与原 10000 集去重移除**: 0
- **场景数**: 30

## 1. 各场景配额

| 场景 ID | 名称 | 配额 | 入选 |
|---|---|---|---|
| 01-low-power | 低电模式 | 204 | 204 | [OK] |
| 02-earphone-music | 耳机音乐 | 204 | 204 | [OK] |
| 03-anti-addiction | 防沉迷 | 185 | 185 | [OK] |
| 04-focus | 专注模式 | 185 | 185 | [OK] |
| 05-agenda | 议程提醒 | 205 | 205 | [OK] |
| 06-memory-clean | 内存清理 | 186 | 186 | [OK] |
| 07-sports-event | 赛事提醒 | 186 | 186 | [OK] |
| 08-sleep | 睡眠卡片 | 196 | 196 | [OK] |
| 09-weather-care | 天气关怀 | 205 | 205 | [OK] |
| 10-rainy-taxi | 雨天打车 | 196 | 196 | [OK] |
| 11-fitness | 运动健身 | 166 | 166 | [OK] |
| 12-finance | 记账理财 | 157 | 157 | [OK] |
| 13-health-reminder | 喝水吃药提醒 | 157 | 157 | [OK] |
| 14-commute | 通勤导航 | 157 | 157 | [OK] |
| 15-smart-home | 智能家居 | 157 | 157 | [OK] |
| 16-travel-ticket | 票务行程 | 157 | 157 | [OK] |
| 17-queue | 排队叫号 | 147 | 147 | [OK] |
| 18-carpool | 拼车出行 | 147 | 147 | [OK] |
| 19-photo-album | 相册管理 | 147 | 147 | [OK] |
| 20-notif-aggregate | 通知聚合 | 157 | 157 | [OK] |
| 21-stocks | 股票基金 | 157 | 157 | [OK] |
| 22-express | 快递物流 | 157 | 157 | [OK] |
| 23-countdown | 倒计时纪念日 | 157 | 157 | [OK] |
| 24-todo | 待办清单 | 166 | 166 | [OK] |
| 25-reading | 阅读听书 | 137 | 137 | [OK] |
| 26-group-buy | 拼单团购 | 147 | 147 | [OK] |
| 27-utility-bill | 水电缴费 | 147 | 147 | [OK] |
| 28-veggie-price | 菜价比价 | 137 | 137 | [OK] |
| 29-elderly-care | 老人关怀看护 | 157 | 157 | [OK] |
| 30-pet-feeder | 宠物喂食 | 137 | 137 | [OK] |

## 2. 12 轴覆盖度

| 轴 | 枚举值 | 原 10000 配额 | 实际 | 状态 |
|---|---|---|---|---|
| size | 2x2 | 4500 | 2514 | [WARN] 缺 1986 |
| size | 2x4 | 4500 | 2486 | [WARN] 缺 2014 |
| component | Progress | 900 | 451 | [WARN] 缺 449 |
| component | Button | 900 | 541 | [WARN] 缺 359 |
| component | Text | 700 | 505 | [WARN] 缺 195 |
| component | Image | 700 | 480 | [WARN] 缺 220 |
| component | Row | 700 | 559 | [WARN] 缺 141 |
| component | Column | 700 | 531 | [WARN] 缺 169 |
| component | Stack | 450 | 477 | [OK] |
| component | Divider | 400 | 489 | [OK] |
| component | List | 400 | 506 | [OK] |
| component | Checkbox | 350 | 461 | [OK] |
| binding | expression | 2500 | 1494 | [WARN] 缺 1006 |
| binding | literal | 2000 | 1102 | [WARN] 缺 898 |
| binding | path | 1500 | 1167 | [WARN] 缺 333 |
| binding | formatString | 1500 | 1237 | [WARN] 缺 263 |
| click | none | 1200 | 504 | [WARN] 缺 696 |
| click | clickToCallPhone | 700 | 510 | [WARN] 缺 190 |
| click | deeplink_settings | 350 | 497 | [OK] |
| click | deeplink_weather | 350 | 462 | [OK] |
| click | deeplink_clock | 350 | 503 | [OK] |
| click | deeplink_music | 350 | 494 | [OK] |
| click | deeplink_health | 350 | 509 | [OK] |
| click | intent_calendar | 350 | 486 | [OK] |
| click | intent_navigate | 350 | 506 | [OK] |
| click | intent_setting_switch | 350 | 529 | [OK] |
| data | static | 4000 | 1850 | [WARN] 缺 2150 |
| data | calendar | 2500 | 1632 | [WARN] 缺 868 |
| data | weather | 2500 | 1518 | [WARN] 缺 982 |
| surface | plain | 400 | 685 | [OK] |
| surface | tinted-surface | 400 | 694 | [OK] |
| surface | colored-root | 400 | 771 | [OK] |
| surface | split-surface | 400 | 693 | [OK] |
| surface | image-derived | 400 | 745 | [OK] |
| surface | dark-stage | 400 | 750 | [OK] |
| surface | soft-material | 400 | 662 | [OK] |
| composition | hero-top | 500 | 833 | [OK] |
| composition | hero-left | 500 | 844 | [OK] |
| composition | split-action | 500 | 863 | [OK] |
| composition | paper-panel | 500 | 772 | [OK] |
| composition | meter-focus | 500 | 898 | [OK] |
| composition | ambient-root | 500 | 790 | [OK] |
| status | none | 3000 | 1302 | [WARN] 缺 1698 |
| status | confirm | 1000 | 1108 | [OK] |
| status | warning | 1000 | 1480 | [OK] |
| status | alert | 1000 | 1110 | [OK] |
| gradient | none | 3500 | 1514 | [WARN] 缺 1986 |
| gradient | ambient-band | 1500 | 1148 | [WARN] 缺 352 |
| gradient | temporal-band | 1500 | 1177 | [WARN] 缺 323 |
| gradient | action-fill | 1500 | 1161 | [WARN] 缺 339 |
| asset | icon | 3500 | 1959 | [WARN] 缺 1541 |
| asset | glyph | 2000 | 2284 | [OK] |
| asset | none | 1500 | 757 | [WARN] 缺 743 |
| template | none | 6000 | 2719 | [WARN] 缺 3281 |
| template | row | 450 | 573 | [OK] |
| template | column | 450 | 726 | [OK] |
| template | list | 450 | 982 | [OK] |

## 3. 未达标轴值

- **size=2x2**: 实际 2514 < 配额 4500 (缺 1986)
- **size=2x4**: 实际 2486 < 配额 4500 (缺 2014)
- **component=Text**: 实际 505 < 配额 700 (缺 195)
- **component=Image**: 实际 480 < 配额 700 (缺 220)
- **component=Progress**: 实际 451 < 配额 900 (缺 449)
- **component=Button**: 实际 541 < 配额 900 (缺 359)
- **component=Row**: 实际 559 < 配额 700 (缺 141)
- **component=Column**: 实际 531 < 配额 700 (缺 169)
- **binding=expression**: 实际 1494 < 配额 2500 (缺 1006)
- **binding=path**: 实际 1167 < 配额 1500 (缺 333)
- **binding=formatString**: 实际 1237 < 配额 1500 (缺 263)
- **binding=literal**: 实际 1102 < 配额 2000 (缺 898)
- **click=none**: 实际 504 < 配额 1200 (缺 696)
- **click=clickToCallPhone**: 实际 510 < 配额 700 (缺 190)
- **data=static**: 实际 1850 < 配额 4000 (缺 2150)
- **data=calendar**: 实际 1632 < 配额 2500 (缺 868)
- **data=weather**: 实际 1518 < 配额 2500 (缺 982)
- **status=none**: 实际 1302 < 配额 3000 (缺 1698)
- **gradient=none**: 实际 1514 < 配额 3500 (缺 1986)
- **gradient=ambient-band**: 实际 1148 < 配额 1500 (缺 352)
- **gradient=temporal-band**: 实际 1177 < 配额 1500 (缺 323)
- **gradient=action-fill**: 实际 1161 < 配额 1500 (缺 339)
- **asset=none**: 实际 757 < 配额 1500 (缺 743)
- **asset=icon**: 实际 1959 < 配额 3500 (缺 1541)
- **template=none**: 实际 2719 < 配额 6000 (缺 3281)

注:口语化版 5000 条样本量约原 10000 的一半,部分轴配额未达是预期,实际训练/测试可与原集合并补足。