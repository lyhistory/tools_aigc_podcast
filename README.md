# tools_aigc_podcast —— 把音频做成播客视频（本机离线）

把「你录的 / 合成出来的音频」变成能直接发的竖屏视频：

**封面（或随机背景视频）+ 波形/频谱 + 逐句字幕 + 顶部进度条 + 画面中间「现在谁在说」**

全程只用 ffmpeg + Python，**不用 GPU、不用装 whisper**。
默认全离线（A 用你自己微调的 GPT-SoVITS）；B 嫌自己的声音不好听时，
可以一键换成**免费在线音色**（不用注册的那种，见第六节）。

默认画面是一套「墨金」配色（深墨底 + 金线 + 象牙白衬线字），5 套主题可换；
配色、字体、字号、音色这些「可查阅的值」都收在文末的**附录 A / B / C**里。

> **你平时只需要做一个动作：双击 `podcast_video.bat`。**

---

## 一、目录长这样

**东西进 `input\`，成片出 `output\`**，就这两个文件夹。

```
tools_aigc_podcast\
  podcast_video.bat        <- 双击这个（唯一的入口）
  podcast.py               <- 干活的脚本
  input\                   <- 你要准备的素材，全放这里
    script.example.txt        台词（A: / B: 分块）→ 复制成 script.txt 再改
    script.example.json       声音配置（参考音频、音色）→ 复制成 script.json 再改
    ref\                      A（你）和 B（AI 配音）的参考音频
    broll\                    （可选）背景视频：行车记录仪、风景、屏幕录制
    lines\                    （可选）现成的逐句音频
    lines.txt                 （可选）和 lines\ 配套的一行一句文本
    cover.png                 （可选）整张封面图，jpg / jpeg / webp 也行
    bg.png                    （可选）自动封面的底图（中间的圆和标题照样叠上去）
    circle.png                （可选）圆里那张图，比如你的头像
  output\                  <- 成片和历史产物都在这，可以随时清空重来
```

`input\` 里那三个文件夹各有一个 `_README.txt`，忘了往哪放就看一眼。

仓库只提交 `script.example.txt`、`script.example.json` 和这三个 `_README.txt`。实际的 `script.txt`、`script.json`、参考音频、快捷方式和 `output\` 都由 `.gitignore` 排除，不会上传。

---

## 二、三步出片（A 是你，B 是 AI 配音）

### 第 1 步 · 放参考音频

把一段 **3~10 秒的干净人声**丢进 `input\ref\`。

- A 用你自己的声音 → 放你的参考音频
- B 想要另一种音色 → 再放一份 B 的
- 嫌麻烦 B 干脆不放 → B 就用 A 的音色说话，也能出片

### 第 2 步 · 写脚本

分两个文件写：**台词**放 `script.txt`，**声音**放 `script.json`。两个都在 `input\` 里。

#### 2a. 台词 → `input\script.txt`

复制 `input\script.example.txt`，改名成 **`input\script.txt`**，然后像聊天记录一样写：

```
A:
肉体进不了天堂地狱，信仰的主体是什么？为何感恩上帝赐予的食物？
B:
信仰的主体不是单纯的灵魂，也不是单纯的肉体，而是灵魂与肉体结合的整全的人。
圣经创世记2章7节说：
“耶和华神用地上的尘土造人，将生气吹在他鼻孔里，他就成了有灵的活人。”这里“有灵的活人”原文的意思是“活的魂”——人不是一个拥有魂的物体，
而是一个魂与身体结合的生命体。
A: 标签后面直接跟内容也行，一行里写几句都行。
B:
下面接着写，写几行都不影响断句。
```

规则就三条：

- **`A:` / `B:` = 换人说话**（冒号中英文都认），冒号后面想直接跟内容也可以。
- **台词怎么断行都行**，换行纯粹为了你方便，不影响断句。
- **断句看标点**：`。！？；` 断开，一句一条字幕；`，` 和 `——` 不断句；
  太短的碎片（不足 8 字）自动并回相邻那句；引号里的句号不会被从引号中间切开。

所以「A 一句、B 好几句」直接写就行 —— 不用数条数、不用加引号、不用碰 JSON。

> 说话人写英文名（`A`、`B`、`S1`）最省事；想写中文名（`小明:`）得先在
> `script.json` 的 `speakers` 里定义过，否则会被当成一句普通台词。

#### 2b. 声音 → `input\script.json`

复制 `input\script.example.json`，改名成 **`input\script.json`**，只改这几处：

- `ref` —— 参考音频的路径，例如 `ref/A_ref2_9s.wav`
- `ref_text` —— 那段音频里**原封不动**说的话（一个字都不能差）
- `name` —— 画面中间「现在谁在说」显示的名字（尾巴上的冒号会被自动去掉）
- 想换 B 的音色或引擎 → 见第六节，现成音色清单在**附录 C**
- 想换配色 / 字体 / 字号 → 见**附录 A**、**附录 B**

路径写成相对 `input\`、相对 GPT-SoVITS 仓库根目录、或者绝对路径都认，详见第六节。
另外：**参考音频必须 3~10 秒**，超了会被 GPT-SoVITS 拒绝。

```json
{
  "title": "小镇青年寻神记",
  "gap": 0.4,
  "video": { "theme": "ink", "circle": "logo.jpeg", "sub_size": 0, "font": "" },
  "speakers": {
    "A": { "name": "小镇青年", "ref": "ref/A_ref2_9s.wav", "ref_text": "参考音频里原封不动说的话" },
    "B": { "name": "AI", "engine": "openai", "model": "FunAudioLLM/CosyVoice2-0.5B", "voice": "anna",
           "base_url": "https://api.siliconflow.cn/v1/audio/speech", "api_key": "sk-你的key" }
  }
}
```

- `"video"` 这个块专管画面，**整个块可以不写**：`theme` 是配色主题（附录 A），
  `font` / `sub_size` 是字体字号（附录 B），`circle` / `bg` / `cover` 换成你自己的图（第五节）。
- `speakers.B` 走在线音色时只要 `engine` / `model` / `voice` 三行加 `api_key`；
  音色怎么挑、有哪些可选，见**附录 C**。

`script.json` 里**不用再写台词**了 —— 台词归 `script.txt`。
（老写法 `"lines": [...]` 仍然认，但已经不推荐；见第七节最后一行。）

### 第 3 步 · 再双击一次 `podcast_video.bat`

它会自己读 `input\script.txt`（没这个才退回 `script.json` 的 `lines`）+ `input\script.json`，
一句一句合成，拼成整期音频，再渲染成 **`output\podcast_<日期时间>.mp4`**（不会覆盖上一次的成片）。
跑完窗口会停住，去 `output\` 里拿成片就行。

生成中间会看到 `master.wav` / `timeline.json` —— 那是音频和时间轴，出片要用，别删。

> 改一句台词只要改 `script.txt` 里那几个字，再双击一次就行 —— **不用数条数、不用配对**。
> 唯一还没做的优化是「改一句只重合成那一句」，见第十一节。

> 合成用的是本机这份 GPT-SoVITS（`..\tools_aigc_GPT-SoVITS\GPT-SoVITS-v2pro-20250604`），
> 默认自动找到，**不用配路径**。没显卡也能跑，就是慢一点。

---

## 三、只想先看看画面长什么样（不用真声）

想先确认版式好不好看，跑一次：

```powershell
podcast_video.bat demo
```

十几秒就给你渲一个 **`output\demo_<日期时间>.mp4`**，版式和真品一模一样：封面 + 波形 + 逐句字幕 + 进度条。

> ⚠️ **demo 里的声音是测试音（正弦波），听起来就是「嗡嗡」的** —— 这不是坏了、也不是 bug，
> 它只是给你看版式。要听真声，走上面那三步。

---

## 四、已经有逐句音频了？丢进 `input\lines\`

比如 GPT-SoVITS 的 `tts_out\0001_xxx.wav`、`0002_xxx.wav` …… 把整个目录里的音频丢进 `input\lines\`，
再在 `input\lines.txt` 里**一行一句**写上对应文本，然后双击 bat 即可。

- 音频按**文件名顺序**播放，和 `lines.txt` 按行一一对应
- 不写 `lines.txt` 就拿文件名当字幕（介意就加 `--no-subs`，只要波形 + 进度条）
- 已经有音频就不用再合成，直接出片

---

## 五、两种画面

**画面从上到下永远是这六层（cover / broll 都一样）：**

```
① 顶部进度条（一直在动）
② 标题（全片最大的一行，在最上面）
③ 中间一个大圆（自动封面画的；可以换成你的头像图）
④ 说话人名字（A 说话显示 A 的名字，B 说话就换成 B 的名字 + B 的颜色）
⑤ 波形 / 频谱
⑥ 底部逐句字幕
```

**cover（封面版 · 默认）**
静态封面 + 波形/频谱 + 逐句字幕 + 进度条。不放封面图就自动画一张（深色渐变 + 中间的圆），零素材也能出片。

**broll（随机视频版）**
往 `input\broll\` 丢几段视频，每段随机截 8~15 秒、不够就循环，统一分辨率后拼接，
字幕/波形/进度条照样叠上去。适合「音频 + 随机行车记录仪画面」这种。

> `input\broll\` **里有视频就自动走 broll，空着就是 cover**，不用手动选。
> 规格统一后的片段缓存在 `output\.broll_cache\`。

### 封面想用自己的图（四个档，按需要挑）

| 你想要的效果 | 怎么做 |
| --- | --- |
| 整张封面就是一张图，不要圆、不要自动排版 | 存成 `input\cover.png` |
| 保留中间的圆和标题，只换底图 | 存成 `input\bg.png` |
| 圆里放你的头像 / 照片（自动裁成圆形，外面描一圈主题色） | 存成 `input\circle.png` |
| 中间干脆不要那个圆 | `script.json` 的 `video` 块里写 `"no_circle": true` |

`bg.png` 和 `circle.png` 可以**一起用**：底图是你的照片，圆里再放个头像。
支持 png / jpg / jpeg / webp / bmp；不想改名也行，命令行 `--bg 路径 --circle 路径` 指过去。

配色 / 字体 / 字号都不用敲命令行：写进 `script.json` 的 `video` 块就行，
可选值见**附录 A（配色主题）**和**附录 B（字体与字号）**。默认那套是给正经长内容配的
「墨金」主题 —— 深墨底 + 金线 + 象牙白衬线字，不再是之前的青橙撞色。

---

## 六、B 的声音从哪来（你是 A，B 用现成的）

A 是你自己（你微调的 GPT-SoVITS 权重）。B 要「另一个人」，下面五条路随便挑一条
（**不想折腾就从方案 2 开始**：不用注册、不用 key，改两行配置就有声）。

（下面这些字段都写在 `input\script.json` 的 `speakers.B` 里；`A` 的配置同理在 `speakers.A`。）

> **换之前先听一句**，别猜 —— 音色这事只能靠耳朵：
>
> ```powershell
> podcast_video.bat sample -e google -v zh-CN     （试听片段落在 output\sample_*.mp3）
> ```

现成音色有哪些、试听文件叫什么名，一页都在**附录 C**。

### 方案 1 · 别人的参考音频 + 底模克隆（推荐，纯离线）

跟 A 一样是「参考音频 + 权重」，但 **B 必须用底模**，不能用你微调出来那套 ——
否则 B 会往你自己身上靠，听着还是你。底模你本机就有：

```json
"B": {
  "name": "唠嗑",
  "ref": "ref/B_female_9s.wav",
  "ref_text": "这段音频里原封不动说的话",
  "gpt": "../../tools_aigc_GPT-SoVITS/GPT-SoVITS-v2pro-20250604/GPT_SoVITS/pretrained_models/s1bert25hz-2kh-longer-epoch=68e-step=50232.ckpt",
  "sovits": "../../tools_aigc_GPT-SoVITS/GPT-SoVITS-v2pro-20250604/GPT_SoVITS/pretrained_models/v2Pro/s2Gv2Pro.pth"
}
```

路径三种写法随便写，脚本都认：

- 相对 `input\`（也就是 `script.json` 所在目录）：`ref/B_female_9s.wav`
- 相对 GPT-SoVITS 仓库根目录：`GPT_weights_v2Pro/voice_liuyue-e15.ckpt`、
  `GPT_SoVITS/pretrained_models/v2Pro/s2Gv2Pro.pth`
- 相对 `input\` 往回走：`../../tools_aigc_GPT-SoVITS/GPT-SoVITS-v2pro-20250604/...`（`script.json` 里就是这么写的）
- 绝对路径：`D:/xxx/yyy.wav`

参考音频哪来？**SoulX-Podcast（Apache-2.0）仓库里就自带**，已经裁好、转写好放在 `input\ref\`。
换音色只要把 `speakers.B` 里的 `ref` 和 `ref_text` 两行一起换掉：

```json
"ref": "ref/B_female_9s.wav",
"ref_text": "喜欢攀岩徒步滑雪的语言爱好者，以及过两天要带着全部家当去景德镇做陶瓷的白日梦想家。"
```

`input\ref\` 里已经放了 4 段现成的参考音频（女声 / 男声各一段能直接用的，外加两段待裁的原件），
**哪一段对应哪个音色、逐字的 `ref_text` 是什么，都在附录 C**。
这四个 `ref_text` 都是本机 FunASR 转出来的原文，可以直接抄 —— 但**只有 9.90 秒那两段能直接用**，
另外两个「原件」超过 10 秒、GPT-SoVITS 会拒绝，留着是方便你自己重新裁：

```
<ffmpeg> -y -i input\ref\B_male_mandarin.wav -t 9.9 -ac 1 -ar 24000 input\ref\B_male_9s.wav
```

裁完**必须重新转写**（裁完的那句话和原文对不上了，不重写音色会飘）：

```powershell
podcast_video.bat transcribe
```

它用 GPT-SoVITS 里那份 FunASR（`tools\asr\models\`，本地模型，**不联网、不用装东西**）
把 `input\ref\` 下的音频逐个转成文字打印出来，照着抄进 `ref_text` 就行。
自己新塞一段别人的参考音频进来，也走这一步。

**铁律：参考音频必须 3~10 秒。** 超了 GPT-SoVITS 会直接报错 —— 脚本现在会**提前检查**并打印裁剪命令。

> **参考音频挺好，就是听着「轻佻」怎么办？**
> 轻佻一般不是音色问题，是**语调摆幅**太大（音高忽高忽低、尾音往上挑）。
> 参考音频里那个人当时怎么说话，B 就会怎么说，所以有三个旋钮按顺序试：
>
> 1. `speakers.B` 里加 `"temperature": 0.7`（默认 1.0）—— 降下来语气立刻变平，最管用
> 2. 再加 `"top_k": 10`（默认 15）
> 3. 最后 `"speed": 0.95` —— 稍微放慢，听着更稳
>
> 还嫌不稳，就换一段**更平静**的参考音频：从 `B_female_mandarin.wav` 里另裁 9.9 秒
> （挑她语气最平的那段），裁完记得 `podcast_video.bat transcribe` 重转 `ref_text`。

### 方案 2 · 免费在线音色，不用注册不用 key（首选）

不用参考音频、不用权重、不用申请账号，配置里加两行就行：

```json
"B": { "name": "唠嗑", "engine": "google", "voice": "zh-CN" }
```

`engine` + `voice` 一共就四个组合（google 两个、baidu 两个）：哪个嗓音更沉、
要能连通哪个站点、对应 `output\其他引擎\` 里哪个试听文件，都在**附录 C**。

先试听再定（不用改文件，直接出一个小片段到 `output\`）：

```powershell
podcast_video.bat sample -e google -v zh-CN
podcast_video.bat sample -e baidu  -v 0
```

听着合适，再把上面那两行写进 `input\script.json` 的 `speakers.B`。
`ref` / `ref_text` / `gpt` / `sovits` 那几行留着不用管（走在线引擎时会被忽略）。

- 句间停顿、逐句字幕、波形、进度条、响度对齐**全都照常**，和用 GPT-SoVITS 出来的没区别
- 不想动 `script.json`、只想临时听一遍：
  `podcast_video.bat auto --ai-engine google --ai-voice zh-CN`
  （`--ai-engine` 会把「不是你」的人统一换成这个在线引擎；`--ai-speaker` 默认 `A`，
  也就是「A 是我自己，别动」）
- ✅ 这两个口子一般不吞字；不过**逐句自查/重试对所有在线引擎都生效**（见第十一节），
  防的是服务端偶尔只回小半句 —— 这种错以前脚本是照收的
- ⚠️ 它们是网页朗读用的口子，**会限流**；真报 `HTTP 429` 就歇几分钟再来
- ⚠️ `baidu` 的 `spd`（语速 1~15，默认 5）能写在 `speakers.B.speed` 里；`google` 没有语速开关

### 方案 3 · 在线音色加强版：免费额度 + 一个 key，音色专业得多

方案 2 胜在零门槛，但都只有一个女声、语气偏「翻译朗读」。
想要**真正的播客音色**（成熟、稳、有气口），用 `engine: "openai"` ——
它接的是**任何 OpenAI 兼容的 `/v1/audio/speech` 接口**，国内这几家都送免费额度、注册免费不用绑卡：

还没接、但配置写上去就能用的服务（智谱 / 火山方舟 / OpenAI）和各自的音色见**附录 C**。

**硅基流动那 8 个音色怎么挑**（哪个沉稳、哪个容易显轻佻、本机实测 F0、对应的试听文件名）
见**附录 C**；也可以直接跑 `podcast_video.bat voices`，它会把那张表打在屏幕上。

**同一个 `anna`，两个模型怎么分？—— 看 `model` 那一行**

`voice` 两边都写 `anna`，**唯一区别就是 `model`**。配置长这样：

```json
"B": {
  "name": "AI",
  "engine": "openai",
  "base_url": "https://api.siliconflow.cn/v1/audio/speech",
  "model": "FunAudioLLM/CosyVoice2-0.5B",
  "voice": "anna",
  "api_key": "sk-你的key"
}
```

| | `FunAudioLLM/CosyVoice2-0.5B` | `fnlp/MOSS-TTSD-v0.5` |
| --- | --- | --- |
| 官方定位 | 通用语音合成，8 个音色都能用 | 专门为「播客对话」训的 |
| 听着像 | 稳、清楚、像播报 | 两个人在聊天，气口更自然 |
| 音高摆幅（同一段长句） | 124 Hz | **74 Hz，更平** |
| **中文念得对不对**（14 句实测） | ✅ 逐字正确（只剩数字写法、记/纪这类同音差异） | ❌ **11 句有插字 / 错词** |

两个模型出的都是 24 kHz 单声道 mp3，后面的合成 / 渲染流程**一模一样**，随时能换。
想听差别：`output\voice_test\` 里的 `对比_12_*`（CosyVoice2）和 `对比_13_*`（MOSS-TTSD）。

> ⚠️ **MOSS-TTSD 会自己在句首加字，也会念错词**（2026-10-19 用本机 FunASR 逐句比对 14 句，
> 11 句有实质错误）：第 8 句「这里」前面多一个「D」（听着像「第」）、第 10 句「感恩」念成
> 「而带您的」、第 22 句「哥林多」念成「戈运多」、「重组细胞」念成「虫子细胞」……
> 同样的 anna 换成 CosyVoice2 后**逐字正确** —— 所以**默认用 CosyVoice2**。
> MOSS 只建议在你愿意自己复听校对的时候用，换回去就把 `model` 改回
> `fnlp/MOSS-TTSD-v0.5`（完整对照表见第十一节）。

不想改文件、临时试一次：

```powershell
podcast_video.bat auto --ai-model fnlp/MOSS-TTSD-v0.5
```

> `--ai-model` / `--ai-voice` **单独给就生效**，只会动「本来就走在线引擎」的那个人，
> 不会碰你自己那条 GPT-SoVITS 的路。

`api_key` 三种给法挑一个（**别把 key 发到群里或截图里**）：

1. 直接写在 `script.json` 里（最省事，缺点是文件里有明文）
2. 设一个环境变量 `PODCAST_TTS_KEY`，`script.json` 里就不写 `api_key`
3. 临时用：命令行加 `--ai-key sk-xxxx`

先试听再定（`--ai-key` 不给就用 `script.json` 里那把）：

```powershell
podcast_video.bat voices
podcast_video.bat sample -e openai -v anna
podcast_video.bat sample -e openai -v charles --ai-model fnlp/MOSS-TTSD-v0.5
```

> 报错对号入座：`401/403` = key 不对；`400` = 模型名或音色名不对；
> `404` = `base_url` 写错了（注意结尾就是 `/v1/audio/speech`，**不要再加** `/audio/tts`）。

### 方案 4 · 微软 edge-tts（音色库最全，但这条网络出口被微软挡了）

```json
"B": { "name": "唠嗑", "engine": "edge", "voice": "zh-CN-XiaoxiaoNeural" }
```

微软那套神经网络音色公认最好听，中文有 20 多个：晓晓 / 晓伊 / 晓梦 / 晓墨（女），
云希 / 云健 / 云扬(播音)（男），还有东北小北、陕西小妮。**但这台机器上用不了**：

> **实测（2026-10-15 复核）**：`wss://speech.platform.bing.com/.../readaloud/edge/v1`
> 一律返回 `403 Invalid response status`。把 `Sec-MS-GEC-Version` 从 143 一路换到 152、
> 干脆不带 token、换成普通浏览器 UA —— **全都是 403**。
> 再走本机那个 v2rayN 代理（`127.0.0.1:10808`）重试，出口 IP 和直连**一模一样**。
> 所以不是版本旧、不是 token 算错，是**我们这条网络出口被微软的朗读接口拒了**（机房 IP）。
> 你打开 [speech.platform.bing.com](https://speech.platform.bing.com/) 看到「不提供服务」，是同一件事。
>
> **真想用它**：换一个能过微软的代理节点（家宽出口基本都能过），
> 然后 `podcast_video.bat sample -e edge -v zh-CN-XiaoxiaoNeural` 试一句，响了就能直接用。
> `podcast\_vendor\` 里已经放好新版 edge-tts，不用再 `pip install`。

### 方案 5 · Windows 自带声音（完全离线，音质一般）

```json
"B": { "name": "唠嗑", "engine": "sapi", "voice": "Huihui" }
```

零安装、零素材，但中文只有「慧慧」一个音色，机器味重，适合先把流程跑通。

> 改完台词或音色直接再双击一次 bat。CPU 上每句约 20 秒，六句两分钟左右（全部重做）。

**换音色只改 `input\script.json` 里 `speakers.B` 那几个字段，A 那一段永远不用动。**

音色清单、官方描述、本机实测音高、以及对应的试听文件名，全在**附录 C**
（`podcast_video.bat voices` 也会把硅基那张表打在屏幕上）。这里只记两条命令：

```powershell
podcast_video.bat sample --all                 （当前模型 × 8 个音色，各出一遍到 output\voice_test\<模型>\）
podcast_video.bat sample -e openai -v claire   （只想单独听一个）
```

`output\voice_test\` 顶层那 4 个 `对比_*.mp3` 是用你 `script.txt` 里的真实台词做的同句对照
（12/13 是同一句，只有模型不同）。

**换音色三步**

1. 打开 `input\script.json`，只改 `speakers.B` 里的 `engine` / `model` / `voice`
2. 想先听一句：`podcast_video.bat sample -e openai -v claire --ai-model fnlp/MOSS-TTSD-v0.5`
3. 定了就双击 `podcast_video.bat`

---

## 七、常用参数

命令行里加就行（`podcast_video.bat render --size 1920x1080 ...`）：

| 参数 | 说明 |
| --- | --- |
| `--size` | 画面尺寸，默认 `1080x1920` 竖屏；B 站横屏用 `1920x1080` |
| `--fps` | 帧率，默认 25 |
| `--visual` | `wave` 波形（默认）/ `spec` 频谱 / `both` 都要 / `none` 都不要 |
| `--cover` | 整张封面图；不给就自动生成（也可以直接放 `input\cover.png`） |
| `--bg` | 自动封面的底图（也可以直接放 `input\bg.png`），圆和标题叠在它上面 |
| `--circle` | 圆里那张图（也可以直接放 `input\circle.png`）；不给就画同心圆 |
| `--no-circle` | 封面中间不画那个圆 |
| `--title` / `--subtitle` | 顶部标题（默认读 `script.json` 的 `title`）/ 标题下面那行小字 |
| `--broll` | 背景视频目录，默认 `input\broll\` |
| `--broll-order` / `--broll-limit` | `seq` 按文件名顺序（默认随机）/ 最多用几段 |
| `--scrim` | 下半部分压暗程度 0~1，字幕在亮画面上看不清就调大 |
| `--no-progress` | 关掉顶部进度条 |
| `--no-subs` | 不烧字幕 |
| `--speaker-tag` | 左上角**也**显示「现在谁在说」（默认不显示，画面中间已经有名字了） |
| `--name` | 字幕每句前面再加上说话人名字（默认不加，中间已经有大字名字了） |
| `--font` | 字体名；不给就自动挑（本机装了思源宋体就用它）。可选清单见**附录 B** |
| `--sub-size` | 字幕字号（像素）。`0` 或不给 = 自动（竖屏 1080x1920 → 70，横屏 1920x1080 → 52） |
| `--title-size` / `--who-size` | 标题字号 / 中间说话人名字的字号，`0` 或不给 = 自动 |
| `--who-y` | 说话人名字在画面高度上的位置，默认 `0.455`（调小往上、调大往下） |
| `--theme` | 配色主题：`ink`（默认）/ `celadon` / `moon` / `clay` / `classic`，见**附录 A** |
| `--accent` | 只覆盖主题色（圆环 / 波形 / 进度条）；默认跟主题，`ink` 是 `C8A45C` 金 |
| `--sub-color` | 字幕颜色：不给 = 跟主题（象牙白），`speaker` = 按说话人上色，或写 `#RRGGBB` |
| `--preset` / `--crf` | x264 参数；想快速试跑就 `--preset veryfast --crf 24` |
| `--no-normalize` | 关掉响度归一。默认会归一到 **-16 LUFS**（播客标准），顺手解决「TTS 声音偏小」 |
| `--no-match-level` | 关掉「按说话人对齐音量」（**默认是开的**，见第十一节） |
| `--match-target` | 对齐到多少 LUFS，默认 `-20` |
| `--synth-retry` | 某句明显太短（吞字）或明显太长（念重了）时最多重合成几次，默认 `2`；在线引擎在这之前还会先掐掉句首/句尾的底噪气口（见第十一节）；`--no-synth-check` 关掉自查重试 |
| `--split-clauses` | 保险模式：按逗号切小口、逐小口合成，丢字概率最低，代价是语速慢一些（见第十一节） |
| `--ai-engine` | 把「不是你」的人整体换成在线音色：`google` / `baidu` / `openai`（见第六节） |
| `--ai-voice` | 在线音色的名字：google 写 `zh-CN`，baidu 写 `0`，openai 写 `anna` 这种 |
| `--ai-model` | 换模型（如 `fnlp/MOSS-TTSD-v0.5`）；**单独给也生效**，不用再配 `--ai-engine` |
| `--ai-speaker` | 哪几个说话人算「我自己」，默认 `A`；这几个的 engine / voice / model 一律不动 |
| `--ai-key` / `--ai-base` | `engine=openai` 的 key / 接口地址 |
| `--debug` | 把整条 ffmpeg 命令打出来，方便自己改 |

### 不想敲命令？画面参数都写在 `script.json` 里

双击 bat 的人不用碰命令行：在 `input\script.json` 里加一个 `"video"` 块就行
（命令行给了的参数优先）。路径都相对 `input\`：

| key | 说明 |
| --- | --- |
| `"title"` / `"subtitle"` | 顶部标题 / 标题下面那行小字 |
| `"bg"` / `"circle"` / `"cover"` | 底图 / 圆里那张图 / 整张封面 |
| `"no_circle"` | `true` = 中间不画圆 |
| `"theme"` | 配色主题：`ink` / `celadon` / `moon` / `clay` / `classic`，见**附录 A** |
| `"sub_size"` | 字幕字号：`0` = 自动（竖屏 1080x1920 → 70），默认就是自动 |
| `"title_size"` / `"who_size"` / `"who_y"` | 标题字号 / 说话人名字字号 / 名字位置，`0` = 自动 |
| `"font"` | 字体名；空着 = 自动挑（本机是思源宋体），清单见**附录 B** |
| `"sub_color"` | 字幕颜色：不写 = 跟主题，`"speaker"` = 按说话人，或写 `"#RRGGBB"` |
| `"sub_margin"` | 字幕离底部的高度，默认 `0.045` |
| `"scrim"` | 下半部分压暗程度，默认 `0.45` |
| `"accent"` | 只覆盖主题色；不写就跟着 `theme` |
| `"visual"` | `wave` / `spec` / `both` / `none` |
| `"speaker_tag"` | `true` = 左上角也显示谁在说 |
| `"progress"` | `false` = 关掉顶部进度条 |
| `"size"` / `"fps"` | 画面尺寸 / 帧率 |

能直接抄的完整样板在 `input\script.example.json`。

命令除了 `auto` / `build` / `render` / `demo` / `from-lines` / `transcribe`，
还有两个和音色有关的（都不会碰成片）：

- **`voices`** —— 列出现成音色，哪个适合播客（附录 C 那张表）
- **`sample`** —— 试听某个音色，结果是 `output\sample_*.mp3`
- **`sample --all`** —— 一次把那个模型的 8 个音色全出一遍，落到 `output\voice_test\<模型>\`

```powershell
podcast_video.bat voices
podcast_video.bat sample --all
podcast_video.bat sample -e openai -v anna
podcast_video.bat sample -e openai -v charles --ai-model fnlp/MOSS-TTSD-v0.5
podcast_video.bat sample -e google -v zh-CN
podcast_video.bat sample -e baidu  -v 0
```

`script.txt` 是纯台词，不带别的设置。想按句微调得用老的 `script.json` 的 `lines` 写法：
`audio`（这句直接用现成音频，跳过合成）、`gap_after`（这句之后的停顿秒数）。
整期的句间停顿统一在 `script.json` 顶上写 `"gap": 0.4`。

---

## 八、产物长什么样

```
output\
  lines\          0001_A.wav 0002_B.wav ...   每句一个文件，都是 32kHz 单声道
  master.wav      整期音频（句间按 gap 插静音）
  timeline.json   时间轴：每句的 speaker / 文本 / 起止秒数 / 文件名 / 增益(dB)
  voice_test\     sample / sample --all 出来的试听片段（挑音色的菜单，随时可删）
  subs.ass        渲染时生成的字幕（可以改样式再手动渲染）
  podcast_20261014_2139.mp4   成片：文件名带日期时间，跑多少次都不会互相覆盖
                              （demo 跑出来的是 demo_20261014_2139.mp4，
                                同一分钟里再跑一次会加序号 _2 / _3）
```

---

## 九、为什么字幕永远不会对不齐

音频是**一句一句合成**的，每句多长、从第几秒开始，在拼接 `master.wav` 的时候就已经算出来了，
写进 `timeline.json`。字幕、进度条、左上角「现在谁在说」全部读这张表。

所以**不用跑 ASR**，也不存在「字幕和声音差半句」这种问题。

> 附带好处：想换画面（封面版 ↔ broll 版）而音频不动，直接
> `podcast_video.bat render --timeline output\timeline.json` 再渲一遍就行。

---

## 十、几个小坑

- **`script.txt` 里的 `A:` / `B:` 标签不会被念出来**，它只管「这句谁说的」。
  标签行和台词混着写没问题，但台词前面必须先用一行标签标出说话人，否则脚本会报错告诉你第几行。
- **句号和引号**：`…有灵的活人。”` 这种会把引号收进同一句，不会从引号中间切。
- **中文说话人**：只有先在 `script.json` 的 `speakers` 里定义过，`小明:` 才会被当成换人。
- **ffmpeg**：脚本会自动找带 libx264 的完整版（这台机器上是
  `D:\Workspace\AI\win-pyvideotrans-v3.86\ffmpeg\ffmpeg.exe`）。
  GPT-SoVITS 自带的 `runtime\ffmpeg.exe` 编译时去掉了 libx264，**导不出通用 MP4**，脚本会自动跳过它。
  你也能用 `--ffmpeg` 或环境变量 `PODCAST_FFMPEG` 指一个。
- **画面里没有数字人对口型**，也没做逐字卡拉 OK 字幕 —— 需要的话得再加一步（强制对齐 / SadTalker 之类）。
- **长节目（>30 分钟）** 建议 `--preset veryfast`，或者先渲低清版看版式。
- **B 是拿别人的声音克隆的**：SoulX-Podcast 那两段示例音频虽然仓库是 Apache-2.0，
  但要不要用在会公开发布的节目里，请你自己再确认一次。

---

## 十一、电平对齐与后续优化

### 已完成 · 按说话人对齐音量（默认开）

响度归一（loudnorm）只在**整期**上做一次，保证「整期平均 = -16 LUFS」，
但它**不会**把 A 和 B 拉到同一个音量档。之前实测 A 约 -32.8 LUFS、B 约 -22.9 LUFS，
**B 比 A 响 10 dB**（「dB」是音量差单位，差 3 dB 耳朵就能听出来，差 10 dB 就是「一个正常说话、一个在喊」）。

现在合成的时候就会先对齐：同一个人取各句响度的**中位数**，抬/压到 `--match-target`（默认 -20 LUFS），
然后再拼 `master.wav`。**同一个人共用一条增益**，所以句内该轻该重的起伏不会被抹平。

| 说话人 | 对齐前 | 对齐后 |
| --- | --- | --- |
| A 小希 | 约 -32.8 LUFS | 约 -21.0 LUFS |
| B 唠嗑 | 约 -22.9 LUFS | 约 -20.5 LUFS |

差 0.5 dB，两个人终于是「同一个音量档」了。

- 峰值会留 1 dB 余量（用 `ebur128` 量峰值再夹住增益），不会削顶
- 想关掉：`--no-match-level`；想换目标：`--match-target -18`
- 每句实际用的增益记在 `output\timeline.json` 的 `gain_db` 里，方便对账

### 已完成 · 丢字自查（默认开）

GPT-SoVITS 是自回归模型，偶尔会「念一半就收」，把一句的尾巴吞掉 ——
之前你听到「…将生气吹在他鼻孔里，他就成了〔有灵的活人〕」里最后几个字没了，就是这种。
**在线引擎（硅基的 MOSS-TTSD 这类）也会**：整段只回一小截，或者反过来拖得老长。

现在的做法：**每句合成完立刻量一下时长**，和中文字数「应有」的时长比（实测约 5 字/秒）；
短到 60% 以下（吞字）、或长过 2.5 倍（念重了）都算这一遍没合好，重来一次，
最多重试 `--synth-retry` 次（默认 2），留下「离应有长度最近」的那条，
日志里会打一行 `! 第 X-Y 句「…」只出了…秒，换个随机种子重来…`。
本机 GPT-SoVITS 和在线引擎走的是同一套标准。

> **实测**（同一句 46 字，4 个小口）：GPT-SoVITS 内部本来就会按逗号切成 4 小口分别合成。
> 整句一次调用，4 次里都没丢字；改成逐小口合成后，「丢一整小口」在物理上不可能发生，
> 但语速会慢一些（同一句：整句 9.8 秒 / 逐小口 12.5 秒）。
> 所以默认是「整句 + 事后自查」；**要是还听到丢字，再加 `--split-clauses` 走保险模式**。
> 保险模式慢掉的那点可以用 `--speed`（比如 1.1~1.2）找回来，自己听着调。

- 固定了种子（`"seed"` 或 `--seed`）时不重试 —— 重试也是同一份结果，白白花时间
- 想彻底关掉自查：`--no-synth-check`

### 已完成 · 在线引擎的「滋滋」底噪与吞句

`podcast_20261016_1703.mp4` 那一版你听到的三件事（19~20 秒的滋滋声、开头像多念了一个字、
整段跳过），根因是同一个：**在线引擎回来的音频没做任何质检就直接拼进去了**。
逐句量出来的证据（用 20ms 一帧的 RMS 包络扫的）：

| 你听到的 | 哪一句 | 原始音频 | 真相 |
| --- | --- | --- | --- |
| 19~20 秒一段「滋滋滋」，开头像多念了一个字 | 第 6 句 | 11.26 秒 | 开头 **2.5 秒**是 −40~−50dB 的宽带底噪（后面还跟着一段纯数字静音），话音第 3 秒才开始 |
| 「感恩食物不是矛盾…」整段跳过 | 第 10 句 | **0.70 秒**（28 字） | 服务端只回了一小截，真正有声的只有 0.26 秒 |
| 「保罗在哥林多前书15章…」整段跳过 | 第 22 句 | **1.18 秒**（38 字） | 同上，只回了开头一点点 |
| 「这必朽坏的总要变成不朽坏的。」慢得离谱 | 第 12 句 | 12.70 秒（13 字） | 这一遍反过来拖长了，字与字之间塞满长停顿 |

现在的处理（默认全开，不用加参数）：

- **掐底噪**：按「比这句最响处低 25dB」判定（不看绝对音量，所以安静的一句也不会被切没），
  句首的底噪、气口整段切掉；再补两道保险：句首/句尾那段「纯静音」（mp3 解码出来是
  −95dB 左右，所以阈值放在 −70dB）连同它外侧明显更轻的那截一起切，句尾整段静音也清掉；
  真正的话音一个字不动 —— 判据特意加了「外侧那截确实不像话音」才动手，
  所以「轻声开头 + 停顿 + 大声正文」这种念法不会被误删（本机 A 的声音不过这道）
- **吞字自查**：短于应有长度的 60%、或长过 2.5 倍，都重合成一遍，取最像样的那条；
  连着几遍都对不上会在日志里**点名第几句**，不会闷声拼进去
- **顺手清理**：`output\lines\` 现在只留这一版时间轴真的会用到的那几句，
  上一版脚本剩下的 `003_B.wav` 这类不再堆在里面（它是复听/排查问题时最大的干扰）

> 为什么以前没拦住：本机 GPT-SoVITS 那条路一直有自查（上一节），
> 在线引擎那条路是拿到文件直接落盘，「整句只回 0.7 秒」这种没人管。

### 已完成 · 关掉 onnxruntime 那条噪音

没显卡的机器上，GPT-SoVITS 每次加载都会去找一遍 CUDA 库，然后在日志里刷一条：

```
[E:onnxruntime:Default, ...] LoadLibrary failed with error 1114 ...
  onnxruntime_providers_cuda.dll
```

这是 onnxruntime 找不到 CUDA（这台机器本来就没有）的例行抱怨，**跟合成没关系**，
合成照样走 CPU。

> **注意：之前那次「压掉」其实没生效**（2026-10-15 抓到的）。
> `podcast.py` 是在 import GPT-SoVITS **之前**把日志级别压到 fatal 的，
> 但 GPT-SoVITS 自己的 `GPT_SoVITS/text/g2pw/onnx_api.py` 第 21 行写着
> `onnxruntime.set_default_logger_severity(3)` —— import 的时候又给改回了 error，
> 所以那条 `[E:onnxruntime …]` 照样会冒出来。
> 现在改成 **import 完再压一次**，实测整条流水线跑完这条日志零命中。

### 已完成 · B 换成免费在线音色（不用 GPU、不用参考音频）

原先是「B 也得给一段别人的参考音频 + 底模克隆」——找音频、裁 3~10 秒、转写 `ref_text`，
一步不对音色就飘，而且挑不到「不轻佻」的那一档。

现在 `speakers.B` 里加两行 `engine` / `voice` 就行，先 `sample` 试听、听着合适再写进配置：

- `google` / `baidu`：**零门槛** —— 免费、不用注册、不用 key、国内可用（第六节方案 2）
- `openai`：接任何 OpenAI 兼容的 `/v1/audio/speech`，硅基流动 / 智谱 / 火山方舟都送免费额度，
  音色专业得多（第六节方案 3）。硅基流动那两个模型各有 8 个预置音色，
  `anna`（沉稳女声）和 `charles`（磁性男声）最适合念稿子，`podcast_video.bat voices` 能列出来
  （表里带官方描述 + 本机实测音高，音色名写短名就行，脚本会自动补成 `模型名:音色`）
- `edge`：音色库最全，但这条网络出口被微软 403 挡着（第六节方案 4 里写了完整实测过程）

在线引擎和本机 GPT-SoVITS 现在走同一套质检：**句首/句尾的底噪与气口先掐掉，
再按「该多长」自查一遍、不对就重合成**（做法和实测数据见第十一节），
而**句间停顿、逐句字幕、波形、进度条、按说话人的响度对齐全都照常**，
成片和走 GPT-SoVITS 出来的没有任何区别。

### 已完成 · B 的模型换成 CosyVoice2（MOSS 会自己加字）

2026-10-19 那版（`podcast_20261019_1839.mp4`）里你听到的「第」「而代音」，不是裁切问题，
也不是听错 —— 是 **MOSS-TTSD 自己念错的**。用本机 FunASR 把 14 句 B 全部转写、
再和台词逐字比对，11 句有实质错误：

| 句 | ASR 转写（节选） | 问题 |
| --- | --- | --- |
| 6 | 供信仰的主体… | 句首多「供」 |
| 7 | 活圣金创世纪… | 多「活」；「圣经」→「圣金」 |
| 8 | D这里有零的活人… | 句首多一个「D」（就是那声「第」）；「有灵」→「有零」 |
| 10 | 而带您的食物不是矛盾… | 「感恩」→「而带您的」（就是「而代音」） |
| 11 | 殊徒保罗在哥林的前书… | 「使徒」→「殊徒」，「多」→「的」，「种」→「中」 |
| 12 | 这必损坏的总要变成不损坏的 | 「朽」→「损」 |
| 17 | 如您问到的那关键点 | 句首多「如您」 |
| 19 | 问，您现在我直接回答… | 句首多「问您」 |
| 20 | 辙这意味着… | 句首多「辙」 |
| 22 | 保罗在戈运多前书…虫子细胞… | 「哥林多」→「戈运多」，「重组」→「虫子」，「机械」→「基械」 |
| 23 | 他必具体如何实现，圣亲没有说明 | 「至于」→「他必」，「圣经」→「圣亲」 |

同样这几句换成 **CosyVoice2 + 同一个 `anna`**，转写逐字正确
（「感恩食物不是矛盾」「这里有灵的活人」「哥林多前书 15 章…重组细胞…神随自己的意思」全对）。

所以 `script.json` 的 `model` 已换成 `FunAudioLLM/CosyVoice2-0.5B`，想换回去只改这一行。
另外 CosyVoice2 出来的电平比 MOSS 低十几 dB，**按说话人对齐音量那一步会自动补平**
（这次 A +12.0dB / B +10.8dB，两个人最后都落在 −20 LUFS），不用手动调。

> 自己校一遍（本机 FunASR，不联网，14 句约 20 秒）：
> ```powershell
> podcast_video.bat transcribe --dir output\lines
> ```
> 输出的每行和 `input\script.txt` 一对，就能看出有没有插字、错词、吞句。

### 已完成 · 画面改版（标题置顶 + 说话人名字居中 + 支持自己的图）

原来的版式和你要的正好差一层：标题画在圆的**下面**，左上角一个小字写着谁在说话。现在改成：

- **标题挪到最上面**（进度条下面），全片最大的一行，cover / broll 都有
- **原来标题的位置改成「现在谁在说」**：居中、大字，跟着说话人换名字和颜色（第五节那张分层图）
- 左上角那个小标签默认**关掉**了（中间已经有大字名字了），想要回来加 `--speaker-tag`
- 标题和名字都不再画进封面图里，改完 `script.json` 重跑就生效，不用重新出图
- **封面支持你自己的图**：`input\bg.png` 当底图、`input\circle.png` 放进中间的圆
  （方形图自动裁圆 + 描一圈主题色）、`input\cover.png` 整张通吃；`--no-circle` 干脆不要圆
- **字幕调大了**：默认从画面宽的 5.5% 提到 6.5%（1080 宽 = 70 号），
  字号 / 字体都能在 `script.json` 的 `video` 块里写死（`sub_size` / `font`）

### 已完成 · 配色与字体改版（不再青橙撞色）

之前是「青色 + 橙色」高饱和撞色配粗黑体，念正经内容很出戏。现在整套换了：

- **默认主题「墨金」（`ink`）**：深墨底 + 金色线（圆环 / 波形 / 进度条）+ 象牙白字幕；
  一共 5 套主题随便换，见**附录 A**
- **字幕不再一个颜色对一个人**：默认整片一个象牙白（最干净）；
  想要老风格写 `"sub_color": "speaker"`
- **默认字体自动挑衬线**：本机装了思源宋体就用它（`Noto Serif SC`），可选清单见**附录 B**
- **封面重画**：一片没有接缝的墨色渐变 + 圆后面一层很淡的暖光晕
  （旧版在 42% 高度换了一次渐变，画面上就是一道横杠）
- **波形换成 `scale=sqrt`**：小音量也看得见，收细了染色，不再是一坨发灰的暗色块
- **标题置顶、名字居中、进度条压淡**：让字幕和标题是画面上最亮的东西

### 还没做 · 逐句缓存（省时间）

**现在的问题**：改一句台词，整期都要重做。CPU 上每句约 20 秒，六句两分钟；
一期 30 句就是 10 分钟以上，为了一个错别字重来一次很肉疼。

**打算怎么做**：给每句算一个指纹（说话人 + 文本 + 音色 + 参考音频 + 权重 + 语速……），
指纹没变就直接复用 `output\lines\` 里上次的结果，只重做真正改过的那几句。
做完之后，二期改一句台词大约就是几十秒出片。

### 还没做 · 出片前自动校字（ASR 自查）

**现在的问题**：TTS 偶尔会把字念错、念重，或者念成另一个词（第十一节那张表就是实例）。
时长自查只能发现「少了一大段」，发现不了「念错一个词」—— 那种错只有人耳（或 ASR）能听出来。

**打算怎么做**：合成完、拼时间轴之前，用本机 FunASR 把每句转写一遍，和台词逐字比对
（数字写法、标点、记/纪这类同音先归一化），相似度低于阈值就重合成，几次不行就在日志里点名。
FunASR 已经在 `transcribe` 里用上了、模型也是现成的，代价约每句 1 秒；
加进来之后，「插字 / 错词」这类问题不用等你听完整期才发现。

**暂时怎么自己查**：`podcast_video.bat transcribe --dir output\lines`，对照 `input\script.txt` 看一遍。

---

## 附录 A · 配色主题（`theme`）

写在哪：`script.json` 里 `"video": { "theme": "ink" }`（顶层直接写 `"theme"` 也认），
或者命令行 `podcast_video.bat render --theme celadon`。**不写就是 `ink`。**

| `theme` | 气质 | 主题色 `accent` | 说话人取色（A / B / C…） | 字幕 |
| --- | --- | --- | --- | --- |
| `ink`（默认） | 墨金 · 书卷气，哲学 / 宗教 / 长文 | `C8A45C` 金 | `EFE7D2` 象牙 / `D9B471` 金 / `A9C4B4` 灰绿 | `F3EDDF` 象牙白 |
| `celadon` | 青瓷 · 淡雅中式 | `7FA89B` | `E8EFE9` / `9CC9B8` / `D5C9A8` | `EEF3EC` |
| `moon` | 月白 · 冷静，偏科技 / 理性 | `7FB2C9` | `E4ECF1` / `A8CBE0` / `C9BFA6` | `EDF2F6` |
| `clay` | 陶土 · 温暖人文，偏生活 / 情感 | `B5713F` | `EFE3D4` / `D3A071` / `A8BCA8` | `F1E8DC` |
| `classic` | **旧版**：青 + 橙高饱和 | `00E5FF` | `00E5FF` / `FFA733` / `7CFC9A` … | 按说话人上色 |

一个主题管四样东西：**主题色**（顶部进度条 / 圆环 / 波形）、**各说话人的取色**
（按 `A` / `B` / `C` 顺序）、**字幕颜色**。

想微调：

| 想要的效果 | 怎么写 |
| --- | --- |
| 整套换一个风格 | `"video": { "theme": "celadon" }` |
| 只换主题色，别的不动 | `"video": { "accent": "#8B6F3E" }` 或 `--accent 8B6F3E` |
| 字幕也按说话人上色（老风格） | `"video": { "sub_color": "speaker" }` |
| 字幕固定成一个颜色 | `"video": { "sub_color": "#EFE7D2" }` |
| 某个人单独指定颜色 | `speakers.B` 里加 `"color": "#D9B471"` |

> 颜色写 `#RRGGBB` 或 `RRGGBB` 都认，大小写无所谓。

---

## 附录 B · 字体与字号（`font` / `sub_size` / …）

### 字号：`sub_size: 0` 就是「按画面自动算」

`0`（或者干脆不写）表示**按短边自动算**，不用你猜该填多少：

| 画布 | 字幕 | 顶部标题 | 中间的名字 |
| --- | --- | --- | --- |
| `1080x1920`（竖屏，默认） | **70** | 54 | 77 |
| `1920x1080`（横屏，B 站那种） | **52** | 40 | 58 |

想写死就填像素值：`"sub_size": 64` 比自动小一点，`"sub_size": 80` 更大。

| 键（写在 `video` 块里） | 默认 | 说明 |
| --- | --- | --- |
| `"sub_size"` | `0` = 自动 | 字幕字号 |
| `"title_size"` | `0` = 自动 | 顶部标题字号（自动 = 短边 × 0.050） |
| `"who_size"` | `0` = 自动 | 画面中间说话人名字的字号（自动 = 短边 × 0.072） |
| `"who_y"` | `0.455` | 名字在画面高度上的位置：`0.25` 往上、`0.6` 往下 |
| `"sub_margin"` | `0.045` | 字幕离底边的高度（占画高） |

### 字体：`font` 空着就自动挑

自动顺序是 `Noto Serif SC`（= 思源宋体）→ `Source Han Serif SC` → `思源宋体` →
`华文中宋` → `STZhongsong` → `Noto Sans SC` → `DengXian` → `Microsoft YaHei`，
挑第一个本机装了的。**这台机器上命中的是思源宋体**，最有书卷气。

本机实测能用（libass 认这些名字，写进 `"font"` 就生效）：

| 写这个 | 是什么 | 感觉 |
| --- | --- | --- |
| `Noto Serif SC` | 思源宋体 | **默认**，宋体衬线，最稳最书卷 |
| `华文中宋` / `STZhongsong` | 中宋 | 比思源宋体粗一点，标题感强 |
| `华文宋体` / `SimSun` | 宋体 | 传统宋体，字号小的时候发虚 |
| `楷体` / `KaiTi` / `华文楷体` | 楷体 | 手写感，适合引文、经文 |
| `华文仿宋` / `FangSong` | 仿宋 | 古籍 / 公文味，笔画偏细 |
| `华文新魏` | 新魏 | 书法味重，只适合标题 |
| `Microsoft YaHei` / `微软雅黑` | 雅黑 | 无衬线，现代但偏「网页」 |
| `SimHei` / `黑体` | 黑体 | 无衬线，最直白 |
| `DengXian` / `等线` | 等线 | 细无衬线，偏轻 |
| `Noto Sans SC` | 思源黑体 | 干净的无衬线 |
| `华文细黑` | 细黑 | 细无衬线 |

⚠️ **`Source Han Serif SC` 不要写** —— 名字看着像思源宋体，但这台机器上它会**回退成黑体**
（实测渲染过）。要思源宋体就写 `Noto Serif SC` 或 `思源宋体`。

> 想把名字填准，先看这台机器装了什么：
> ```powershell
> Get-ChildItem $env:windir\Fonts -Include *.ttf,*.ttc,*.otf -Recurse | Select-Object -ExpandProperty Name
> ```
> 或者直接把名字填进 `"font"` 跑一次 `podcast_video.bat demo`，看渲出来是不是你要的那个样子。

---

## 附录 C · 音色速查（B 用哪些现成声音）

正文只讲怎么配，所有清单集中在这里。

### C1 · 免 key 的现成音色（配置就 `engine` + `voice` 两行）

| 试听文件（在 `output\其他引擎\`） | `engine` | `voice` | 音色 | 备注 |
| --- | --- | --- | --- | --- |
| `sample_google-zh-CN_*.mp3` | `google` | `zh-CN` | 普通话女声 | 语气平、不飘，但偏「翻译朗读」 |
| `sample_google-zh-TW_*.mp3` | `google` | `zh-TW` | 台湾国语女声 | 嗓音更沉一点 |
| `sample_baidu-0_*.mp3` | `baidu` | `0` | 百度女声 | 广播腔，国内直连最稳 |
| `sample_baidu-4_*.mp3` | `baidu` | `4` | 百度女声（另一个） | 音调偏高、偏年轻 |
| （这台机器出不了） | `edge` | `zh-CN-XiaoxiaoNeural` 等 20+ 个 | 晓晓 / 晓伊 / 云希 … | 音色库最全，但这条出口被微软 403（第六节方案 4） |
| （还没出过） | `sapi` | `Huihui` | 系统自带慧慧 | 完全离线，机器味重 |

### C2 · 硅基流动那 8 个音色（CosyVoice2 / MOSS-TTSD 共用）

跑 `podcast_video.bat voices` 会把这张表打在屏幕上。**顺序就是推荐顺序**，
F0 是本机实测（同一段 81 字文本，越低越沉稳）：

| 音色 | 性别 | 官方描述 | 实测 F0 中位 | 适合播客吗 |
| --- | --- | --- | --- | --- |
| `anna` | 女 | **沉稳女声** | 225 Hz，音高起伏最小 | ✅ **首推** —— 念稿子最不飘 |
| `claire` | 女 | **温柔女声** | 246 Hz | ✅ 次选，比 anna 软一点 |
| `bella` | 女 | 激情女声 | 254~267 Hz | ⚠️ 偏用力，长篇容易累 |
| `diana` | 女 | 欢快女声 | 276~302 Hz | ⚠️ 「欢快」念正经内容就是那种轻佻 |
| `alex` | 男 | 沉稳男声 | 122~128 Hz | ✅ 男声想要的话先试它 |
| `benjamin` | 男 | 低沉男声 | 107~108 Hz | ✅ 最低沉，很像纪录片旁白 |
| `charles` | 男 | 磁性男声 | 132~135 Hz | ✅ 男声里听起来最「播客」的 |
| `david` | 男 | 欢快男声 | 167~172 Hz | ⚠️ 偏年轻活泼 |

配置：`engine` 写 `"openai"`，`base_url` / `api_key` 不动，只换 `model` + `voice`：

| 先听这个 | `model` 写什么 | `voice` 写什么 | 音色 |
| --- | --- | --- | --- |
| `MOSS-TTSD\01`、`对比_13_*` | `fnlp/MOSS-TTSD-v0.5` | `anna` | 沉稳女声，音高最平 |
| `CosyVoice2\01`、`对比_12_*` | `FunAudioLLM/CosyVoice2-0.5B` | `anna` | 沉稳女声，通用 TTS，更「播报」 |
| `MOSS-TTSD\02` / `CosyVoice2\02` | 上面对应的 model | `claire` | 温柔女声 |
| `MOSS-TTSD\07` / `CosyVoice2\07` | 上面对应的 model | `charles` | 磁性男声 · 男声首选 |
| `MOSS-TTSD\05` / `CosyVoice2\05` | 上面对应的 model | `alex` | 沉稳男声 |
| `MOSS-TTSD\06` / `CosyVoice2\06` | 上面对应的 model | `benjamin` | 低沉男声 |
| `MOSS-TTSD\03` / `CosyVoice2\03` | 上面对应的 model | `bella` | 激情女声 ⚠️ |
| `MOSS-TTSD\04` / `CosyVoice2\04` | 上面对应的 model | `diana` | 欢快女声 ⚠️ 最容易显轻佻 |
| `MOSS-TTSD\08` / `CosyVoice2\08` | 上面对应的 model | `david` | 欢快男声 ⚠️ |

> `CosyVoice2\` 和 `MOSS-TTSD\` 两个文件夹是 `podcast_video.bat sample --all` 生成的
> —— 当前 `script.json` 里那个模型 × 8 个音色各一遍。想重听随时再跑
> `podcast_video.bat sample --all`（换模型加 `--ai-model FunAudioLLM/CosyVoice2-0.5B`）。
>
> ⚠️ **默认选 CosyVoice2，不要选 MOSS-TTSD**：MOSS 会自己在句首加字、也会念错词
> （2026-10-19 实测 14 句里 11 句有实质错误，证据表在第十一节）。
> `MOSS-TTSD\` 里的试听文件仍然可以听音色，但正式出片别用它。
>
> **音色名字怎么写**：硅基要求写成 `模型名:音色`；你只写 `anna` 也行 ——
> 脚本发现接口不认会自动补上模型名，并在日志里打一句 `（音色自动补成了 …）`。

### C3 · 其他 OpenAI 兼容服务（`engine` 一律写 `"openai"`）

| 服务 | `base_url` | 模型写什么 | 起始音色 | 备注 |
| --- | --- | --- | --- | --- |
| 硅基流动 SiliconFlow | `https://api.siliconflow.cn/v1/audio/speech` | `FunAudioLLM/CosyVoice2-0.5B` | `anna` | **默认就是这家**，两个模型都标价 ¥0 |
| 硅基流动（对话感更强） | 同上 | `fnlp/MOSS-TTSD-v0.5` | `anna` | ⚠️ 气口更像聊天，但**会插字/念错词**（实测 11/14 句），别用 |
| 智谱 GLM | `https://open.bigmodel.cn/api/paas/v4/audio/speech` | `glm-tts` | `tongtong`(女) / `xiaochen`(女) | 中文最自然的一档 |
| 火山方舟（豆包） | `https://ark.cn-beijing.volces.com/api/v3/audio/speech` | 方舟控制台里的 TTS 接入点 id | 灿灿 / 爽快思思 … | 音色最多、最像播客 |
| OpenAI | `https://api.openai.com/v1/audio/speech` | `gpt-4o-mini-tts` | `alloy` / `nova` | 中文一般 |

### C4 · 离线克隆用的参考音频（`input\ref\`）

**只有前两段（9.90 秒的）能直接用**；后两段是「原件」，超过 10 秒会被 GPT-SoVITS 拒绝，
留着方便你自己重新裁（裁完必须 `podcast_video.bat transcribe` 重转 `ref_text`）。

| `ref` 就写这个 | 音色 | 时长 | `ref_text` 抄这个（**一个字都不能差**） |
| --- | --- | --- | --- |
| `ref/B_female_9s.wav` | 女声 | 9.90 s | 喜欢攀岩徒步滑雪的语言爱好者，以及过两天要带着全部家当去景德镇做陶瓷的白日梦想家。 |
| `ref/B_male_9s.wav` | 男声 | 9.90 s | 哦，还有一个就是要跟大家纠正一点，就是我们在看电影的时候，尤其是游戏玩家看电影的时候，在看到那个到西北那边的这个陕北民。 |
| `ref/B_female_mandarin.wav` | 女声原件 | 10.04 s | 和上面女声同一段（超了 10 秒，不能直接用） |
| `ref/B_male_mandarin.wav` | 男声原件 | 13.78 s | 哦，还有一个就是要跟大家纠正一点，就是我们在看电影的时候，尤其是游戏玩家看电影的时候，在看到那个到西北那边的这个陕北民谣。嗯，这个可能在想，哎，是不是它是受到了黑神话的启发。 |

裁一段新的（裁完用 `transcribe` 重新转写，不然音色会飘）：

```
<ffmpeg> -y -i input\ref\B_male_mandarin.wav -t 9.9 -ac 1 -ar 24000 input\ref\B_male_9s.wav
```

### C5 · 试听命令

```powershell
podcast_video.bat voices                     （把硅基 8 音色表打在屏幕上）
podcast_video.bat sample -e google -v zh-CN  （出一个试听片段到 output\sample_*.mp3）
podcast_video.bat sample -e openai -v anna
podcast_video.bat sample -e openai -v charles --ai-model fnlp/MOSS-TTSD-v0.5
podcast_video.bat sample --all               （当前模型 × 8 音色，各出一遍）
```
