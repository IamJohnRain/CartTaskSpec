import { SurfaceController, SurfaceEventType, Catalog, UIRendererComponent } from '@arkui-genius/genui'
import { resourceManager } from '@kit.LocalizationKit'
import { util } from '@kit.ArkTS'

@Entry
@Component
struct Index {
  @State controller: SurfaceController | null = null

  aboutToAppear(): void {
    // ① 创建 SurfaceController（basic = A2UI 原生 18 标准组件）
    const catalog = Catalog.extended()
    const callback = (eventType: SurfaceEventType, ctrl: SurfaceController) => {
      console.log(`Event: ${eventType}`)
    }
    this.controller = new SurfaceController(catalog, callback)

    // ② 注册 Action 接收器
    this.controller.registerActionReceiver((action: string) => {
      console.log(`Action received: ${action}`)
    })

    // ③ 读取 rawfile 中的 DSL，逐条投喂给 Controller
    const ctx = getContext(this)
    const resMgr = ctx.resourceManager
    try {
      const fileData = resMgr.getRawFileContentSync('sample.jsonl')
      const textDecoder = util.TextDecoder.create('utf-8')
      const jsonStr = textDecoder.decodeToString(new Uint8Array(fileData.buffer))
      const messages: object[] = JSON.parse(jsonStr)
      for (const msg of messages) {
        this.controller!.onReceive(JSON.stringify(msg))
      }
    } catch (e) {
      console.error(`Failed to read sample.jsonl: ${e}`)
    }
  }

  aboutToDisappear(): void {
    this.controller?.destroy()
  }

  build() {
    Column() {
      UIRendererComponent({ surfaceControllerBound: this.controller })
    }
    .width('100%')
    .height('100%')
    .alignItems(HorizontalAlign.Center)
  }
}
