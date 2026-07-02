# A2UI Query 数据生产覆盖度报告

- **最终有效条数**: 10000
- **原始产出**: 12775
- **精确去重移除**: 0
- **近似去重移除**: 0
- **场景数**: 30

## 1. 各场景配额达成

| 场景 ID | 场景名 | 配额 | 产出 | 入选 | 达成 |
|---|---|---|---|---|---|
| 01-low-power | 低电模式 | 420 | 525 | 420 | ✅ |
| 02-earphone-music | 耳机音乐 | 420 | 525 | 420 | ✅ |
| 03-anti-addiction | 防沉迷 | 380 | 475 | 380 | ✅ |
| 04-focus | 专注模式 | 380 | 475 | 361 | ⚠️ |
| 05-agenda | 议程提醒 | 420 | 525 | 420 | ✅ |
| 06-memory-clean | 内存清理 | 380 | 475 | 375 | ⚠️ |
| 07-sports-event | 赛事提醒 | 380 | 475 | 380 | ✅ |
| 08-sleep | 睡眠卡片 | 400 | 500 | 400 | ✅ |
| 09-weather-care | 天气关怀 | 420 | 525 | 420 | ✅ |
| 10-rainy-taxi | 雨天打车 | 400 | 500 | 400 | ✅ |
| 11-fitness | 运动健身 | 340 | 425 | 340 | ✅ |
| 12-finance | 记账理财 | 320 | 400 | 320 | ✅ |
| 13-health-reminder | 喝水吃药提醒 | 320 | 400 | 320 | ✅ |
| 14-commute | 通勤导航 | 320 | 400 | 320 | ✅ |
| 15-smart-home | 智能家居 | 320 | 400 | 320 | ✅ |
| 16-travel-ticket | 票务行程 | 320 | 400 | 312 | ⚠️ |
| 17-queue | 排队叫号 | 300 | 375 | 245 | ⚠️ |
| 18-carpool | 拼车出行 | 300 | 375 | 299 | ⚠️ |
| 19-photo-album | 相册管理 | 300 | 375 | 298 | ⚠️ |
| 20-notif-aggregate | 通知聚合 | 320 | 400 | 320 | ✅ |
| 21-stocks | 股票基金 | 320 | 400 | 320 | ✅ |
| 22-express | 快递物流 | 320 | 400 | 320 | ✅ |
| 23-countdown | 倒计时纪念日 | 320 | 400 | 292 | ⚠️ |
| 24-todo | 待办清单 | 340 | 425 | 340 | ✅ |
| 25-reading | 阅读听书 | 280 | 350 | 266 | ⚠️ |
| 26-group-buy | 拼单团购 | 300 | 375 | 300 | ✅ |
| 27-utility-bill | 水电缴费 | 300 | 375 | 271 | ⚠️ |
| 28-veggie-price | 菜价比价 | 280 | 350 | 255 | ⚠️ |
| 29-elderly-care | 老人关怀看护 | 320 | 400 | 318 | ⚠️ |
| 30-pet-feeder | 宠物喂食 | 280 | 350 | 248 | ⚠️ |

## 2. 12 轴覆盖度

| 轴 | 枚举值 | 配额下限 | 实际命中 | 状态 |
|---|---|---|---|---|
| size | 2x2 | 4500 | 4924 | ✅ |
| size | 2x4 | 4500 | 5076 | ✅ |
| component | Progress | 900 | 1243 | ✅ |
| component | Button | 900 | 1096 | ✅ |
| component | Text | 700 | 1249 | ✅ |
| component | Image | 700 | 842 | ✅ |
| component | Row | 700 | 1012 | ✅ |
| component | Column | 700 | 1020 | ✅ |
| component | Stack | 450 | 843 | ✅ |
| component | Divider | 400 | 849 | ✅ |
| component | List | 400 | 1037 | ✅ |
| component | Checkbox | 350 | 809 | ✅ |
| binding | expression | 2500 | 3034 | ✅ |
| binding | literal | 2000 | 2164 | ✅ |
| binding | path | 1500 | 2325 | ✅ |
| binding | formatString | 1500 | 2477 | ✅ |
| click | none | 1200 | 1432 | ✅ |
| click | clickToCallPhone | 700 | 1119 | ✅ |
| click | deeplink_settings | 350 | 966 | ✅ |
| click | deeplink_weather | 350 | 756 | ✅ |
| click | deeplink_clock | 350 | 966 | ✅ |
| click | deeplink_music | 350 | 838 | ✅ |
| click | deeplink_health | 350 | 1023 | ✅ |
| click | intent_calendar | 350 | 901 | ✅ |
| click | intent_navigate | 350 | 982 | ✅ |
| click | intent_setting_switch | 350 | 1017 | ✅ |
| data | static | 4000 | 4190 | ✅ |
| data | calendar | 2500 | 2969 | ✅ |
| data | weather | 2500 | 2841 | ✅ |
| surface | plain | 400 | 1336 | ✅ |
| surface | tinted-surface | 400 | 1335 | ✅ |
| surface | colored-root | 400 | 1550 | ✅ |
| surface | split-surface | 400 | 1351 | ✅ |
| surface | image-derived | 400 | 1471 | ✅ |
| surface | dark-stage | 400 | 1604 | ✅ |
| surface | soft-material | 400 | 1353 | ✅ |
| composition | hero-top | 500 | 1618 | ✅ |
| composition | hero-left | 500 | 1697 | ✅ |
| composition | split-action | 500 | 1765 | ✅ |
| composition | paper-panel | 500 | 1548 | ✅ |
| composition | meter-focus | 500 | 1828 | ✅ |
| composition | ambient-root | 500 | 1544 | ✅ |
| status | none | 3000 | 3146 | ✅ |
| status | confirm | 1000 | 1956 | ✅ |
| status | warning | 1000 | 2925 | ✅ |
| status | alert | 1000 | 1973 | ✅ |
| gradient | none | 3500 | 3752 | ✅ |
| gradient | ambient-band | 1500 | 2195 | ✅ |
| gradient | temporal-band | 1500 | 2094 | ✅ |
| gradient | action-fill | 1500 | 1959 | ✅ |
| asset | icon | 3500 | 3947 | ✅ |
| asset | glyph | 2000 | 4386 | ✅ |
| asset | none | 1500 | 1667 | ✅ |
| template | none | 6000 | 6179 | ✅ |
| template | row | 450 | 862 | ✅ |
| template | column | 450 | 1173 | ✅ |
| template | list | 450 | 1786 | ✅ |

## 3. 覆盖度

所有轴值均达到配额下限。