```genui
{"version":"v0.9","createSurface":{"surfaceId":"smart_home_schedule_281","catalogId":"ohos.a2ui.extended.catalog","width":140,"height":140}}
{"version":"v0.9","updateComponents":{"surfaceId":"smart_home_schedule_281","root":"root","components":[{"id":"root","component":"Column","children":["title","hero_row","support_line"],"itemMargin":6,"onClick":[{"call":"clickToDeeplink","args":{"bundleName":"com.huawei.hmos.settings","abilityName":"com.huawei.hmos.settings.MainAbility","uri":"intelligent_scene_entry"}}],"styles":{"width":140,"height":140,"padding":12,"borderRadius":18,"clip":true,"backgroundColor":"#FFFFFFFF","justifyContent":"start","alignItems":"start"}},{"id":"title","component":"Text","content":"今日日程","styles":{"width":116,"height":18,"fontSize":14,"fontWeight":500,"fontColor":"#99000000","maxLines":1,"textOverflow":"none"}},{"id":"hero_row","component":"Row","children":["hero_number","hero_unit"],"itemMargin":4,"wrap":"noWrap","styles":{"width":116,"height":40,"justifyContent":"start","alignItems":"center"}},{"id":"hero_number","component":"Text","content":{"call":"formatString","args":{"value":"${/calendar/completed}"}},"styles":{"width":32,"height":36,"fontSize":32,"fontWeight":800,"fontColor":"#FF64BB5C","maxLines":1,"textOverflow":"none"}},{"id":"hero_unit","component":"Text","content":"项已完成","styles":{"width":80,"height":18,"fontSize":12,"fontWeight":400,"fontColor":"#99000000","maxLines":1,"textOverflow":"none"}},{"id":"support_line","component":"Text","content":{"call":"formatString","args":{"value":"${/calendar/next/time} ${/calendar/next/title}"}},"styles":{"width":116,"height":20,"fontSize":12,"fontWeight":400,"fontColor":"#E5000000","maxLines":1,"textOverflow":"none"}}]}}
{"version":"v0.9","updateDataModel":{"surfaceId":"smart_home_schedule_281","path":"/","value":{"card":{"title":"今日日程"},"calendar":{"count":3,"completed":2,"next":{"time":"14:00","title":"团队站会","entityId":"mock-calendar-smart-home-281"},"items":[{"entityName":"calendar","entityId":"mock-calendar-smart-home-281","title":"团队站会","dtStart":"14:00","dtEnd":"15:00","completed":false}]},"state":{"loading":false}}}}

```
```cardspec
{
  "suggestSize": "2x2"
}

```