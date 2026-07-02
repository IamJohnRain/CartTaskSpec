import json
p = {
  'model': 'MiniMax-M3',
  'temperature': 0.95,
  'messages': [
    {'role':'system','content':'你是数据构造专家'},
    {'role':'user','content':"""你是 HarmonyOS A2UI 服务卡片的真实用户,正在向卡片生成助手提需求。
请围绕【低电模式】场景(电量监控、省电模式)生成 2 条不同的用户 Query。

本批每条 Query 的差异化要求(逐条对应,务必让该 Query 自然体现出对应特征):
第1条要求: 以文字信息为主(标题/数值/状态);需要一键拨打电话的动作
第2条要求: 需要一个进度/比例/环形可视化;需要跳转到系统设置(省电/存储/应用时长等)

硬性要求:
1. 每条 Query 一行,格式「序号. 内容」,序号从1到2,不要空行、不要解释、不要标题。
2. 详略要均衡。
3. 口吻要像真实用户口语,可带情绪、带具体数字、带场景细节。
4. 严格覆盖差异化要求里列出的特征,不要雷同。
5. 禁止输出任何与上述2条无关的内容。

请直接输出 2 条 Query:"""}
  ]
}
open('D:/tmp/opencode/mmx_bench2.json','w',encoding='utf-8').write(json.dumps(p,ensure_ascii=False))
