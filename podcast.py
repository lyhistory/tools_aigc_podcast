#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""podcast.py - 把音频做成播客视频（本机离线，只用 ffmpeg + Python）

  synth   对话脚本 -> master.wav + timeline.json
          台词写在 script.txt 里（A: / B: 分块，想写几行写几行），
          声音设置在 script.json 里（参考音频 / 权重 / 音色）。
          A 用你自己的 GPT-SoVITS 权重/参考音频；B 可以换一套权重，
          也可以直接指现成的配音文件（别的工具生成的都行）。
          逐句合成，所以每句的起止时间是我们自己算的，不用跑 ASR 对字幕。
  render  timeline.json + master.wav -> mp4
          cover 模式: 静态封面(没给就自动生成) + 波形/频谱 + 逐句字幕 + 进度条
          broll 模式: 一个目录里的视频随机当背景(行车记录仪之类) + 字幕/波形/进度条
  build   = synth + render
  demo    造一段假音频 + 时间轴，先看一眼画面（不需要 GPT-SoVITS）

  auto    看 input\ 里有什么就做什么（双击 podcast_video.bat 就是这个）

素材都放进 input\，成片都出到 output\。用法见同目录 README.md。
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import random
import re
import shutil
import subprocess
import sys
import time

VERSION = "1.0"
# 兜底色（有主题时一律以主题为准）：跟默认主题 ink 的金一致，别再用旧的青
DEFAULT_ACCENT = "C8A45C"
SPK_COLORS = ["00E5FF", "FFA733", "7CFC9A", "FF7AB6", "B39DFF", "FFE066"]

# 配色主题：一次定好「主题色（圆环 / 波形 / 进度条）+ 各说话人颜色 + 字幕颜色」
#   colors = A / B / C … 依次取色；script.json 里给某个人写了 "color" 就用他自己的
#   sub    = 字幕正文颜色；None = 字幕也按说话人上色（老的高饱和风格）
THEMES = {
    "ink": {"accent": "C8A45C", "colors": ["EFE7D2", "D9B471", "A9C4B4"], "sub": "F3EDDF"},
    "celadon": {"accent": "7FA89B", "colors": ["E8EFE9", "9CC9B8", "D5C9A8"], "sub": "EEF3EC"},
    "moon": {"accent": "7FB2C9", "colors": ["E4ECF1", "A8CBE0", "C9BFA6"], "sub": "EDF2F6"},
    "clay": {"accent": "B5713F", "colors": ["EFE3D4", "D3A071", "A8BCA8"], "sub": "F1E8DC"},
    "classic": {"accent": "00E5FF", "colors": SPK_COLORS, "sub": None},
}
DEFAULT_THEME = "ink"
_ACTIVE_THEME = None

# 字幕 / 标题的默认字体：从上往下找第一个本机装了的（Noto Serif SC 就是思源宋体，最有书卷气）
FONT_PREFS = ["Noto Serif SC", "Source Han Serif SC", "思源宋体", "华文中宋", "STZhongsong",
              "Noto Sans SC", "DengXian", "Microsoft YaHei"]
SR = 32000
VIDEO_EXTS = (".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv", ".ts", ".wmv", ".mpg", ".mpeg")
IMG_EXTS = (".png", ".jpg", ".jpeg", ".webp", ".bmp")
AUDIO_EXTS = (".wav", ".flac", ".mp3", ".m4a", ".ogg", ".opus", ".aif", ".aiff")
FONT_CANDIDATES = [
    r"C:\Windows\Fonts\msyhbd.ttc",
    r"C:\Windows\Fonts\msyh.ttc",
    r"C:\Windows\Fonts\simhei.ttf",
    r"C:\Windows\Fonts\Deng.ttf",
    r"C:\Windows\Fonts\simsun.ttc",
]
KNOWN_FFMPEG = [
    r"D:\Workspace\AI\win-pyvideotrans-v3.86\ffmpeg\ffmpeg.exe",
    r"D:\Workspace\AI\SmartSub\resources\app.asar.unpacked\node_modules\ffmpeg-static\ffmpeg.exe",
]
LANG_ALIAS = {
    "zh": "all_zh", "cn": "all_zh", "中文": "all_zh",
    "en": "en", "英文": "en",
    "ja": "all_ja", "jp": "all_ja", "日文": "all_ja",
    "yue": "all_yue", "粤语": "all_yue",
    "ko": "all_ko", "韩文": "all_ko",
    "multi": "auto", "多语种混合": "auto",
}

# ------------------------------------------------ 在线现成音色（B 的配音）
AI_UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
         "(KHTML, like Gecko) Chrome/143.0.0.0 Safari/537.36 Edg/143.0.0.0")
AI_ENGINES = ("google", "baidu", "openai")
# engine=openai = 任何 OpenAI 兼容的 /v1/audio/speech；默认按硅基流动填，不对就改这三行
AI_BASE = "https://api.siliconflow.cn/v1/audio/speech"
AI_MODEL = "FunAudioLLM/CosyVoice2-0.5B"
AI_VOICE = "anna"
AI_SAMPLE_TEXT = ("这段是用来试听的。信仰的主体不是单纯的灵魂，也不是单纯的肉体，"
                  "而是灵魂与肉体结合的整全的人。")
# 硅基流动 CosyVoice2 / MOSS-TTSD 两套模型共用这 8 个系统预置音色（官方描述）。
# 列表顺序 = 播客推荐顺序：先沉稳/温柔女声，欢快的往后放。
AI_SF_VOICES = [
    ("anna", "女", "沉稳女声"),
    ("claire", "女", "温柔女声"),
    ("bella", "女", "激情女声"),
    ("diana", "女", "欢快女声"),
    ("alex", "男", "沉稳男声"),
    ("benjamin", "男", "低沉男声"),
    ("charles", "男", "磁性男声"),
    ("david", "男", "欢快男声"),
]
OPENAI_VOICE_NOTE = {"shown": False}

HERE = os.path.dirname(os.path.abspath(__file__))
IN_DIR = os.path.join(HERE, "input")          # 素材都放这
OUT_DIR = os.path.join(HERE, "output")        # 成片都出这
BUNDLE_HINT = os.path.join(os.path.dirname(HERE), "tools_aigc_GPT-SoVITS",
                           "GPT-SoVITS-v2pro-20250604")
GETTING_STARTED = """
============================================================
input\\ 里还没有东西，按这三步来：

  1) 放参考音频
     一段 3~10 秒的干净人声丢进 input\\ref\\（wav / mp3 / m4a 都行）

  2) 写脚本
     台词：把 input\\script.example.txt 复制成 input\\script.txt，然后想怎么写怎么写：
             A:
             你想说的话，写几行都行，换行随便断。
             B:
             对方的话。同一行里写几句也行，脚本会自己按句号切。
     声音：把 input\\script.example.json 复制成 input\\script.json，
           再把里面的 ref / ref_text 换成你自己那份：
             ref       = 参考音频的路径（相对于 input\\script.json）
             ref_text  = 那段音频里原封不动说的话

  3) 再双击一次这个 bat（或者再跑一次 auto）

只想先看画面长什么样、不用真声：  podcast_video.bat demo
已经有逐句音频了：                wav 丢进 input\\lines\\，文本一行一句写进 input\\lines.txt
============================================================"""


# ---------------------------------------------------------------- 小工具
def _fix_console():
    for stream in (sys.stdout, sys.stderr):
        try:
            stream.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass


_fix_console()


def log(msg=""):
    print(msg, flush=True)


def warn(msg):
    print("!! " + msg, flush=True)


def die(msg):
    print("")
    print("!! " + msg)
    print("")
    raise SystemExit(1)


def run(cmd, cwd=None, quiet=False, check=True, stream=False):
    """跑外部命令。失败时把命令和 stderr 尾巴打出来，不然很难查。"""
    if not quiet:
        log("    $ " + " ".join(cmd))
    if stream:
        proc = subprocess.Popen(cmd, cwd=cwd, stdout=subprocess.PIPE,
                                stderr=subprocess.STDOUT, text=True,
                                encoding="utf-8", errors="replace", bufsize=1)
        for line in proc.stdout:
            sys.stderr.write(line)
            sys.stderr.flush()
        proc.wait()
        if check and proc.returncode != 0:
            die("命令失败（退出码 %d）：\n    %s" % (proc.returncode, " ".join(cmd)))
        return None
    p = subprocess.run(cmd, cwd=cwd, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                       text=True, encoding="utf-8", errors="replace")
    if check and p.returncode != 0:
        tail = "\n".join((p.stderr or "").strip().splitlines()[-15:])
        die("命令失败（退出码 %d）：\n    %s\n%s" % (p.returncode, " ".join(cmd), tail))
    return p


def load_json(path):
    with open(path, encoding="utf-8-sig") as f:
        return json.load(f)


def write_json(path, obj):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)


def parse_size(s):
    m = re.match(r"^\s*(\d+)\s*[xX*]\s*(\d+)\s*$", str(s))
    if not m:
        die("--size 要写成 1080x1920 这样，现在是 %r" % (s,))
    w, h = int(m.group(1)), int(m.group(2))
    if w < 2 or h < 2 or w % 2 or h % 2:
        die("--size 的宽高必须是正偶数：%dx%d" % (w, h))
    return w, h


def ass_time(t):
    t = max(0.0, float(t))
    cs = int(round(t * 100))
    h, cs = divmod(cs, 360000)
    m, cs = divmod(cs, 6000)
    s, cs = divmod(cs, 100)
    return "%d:%02d:%02d.%02d" % (h, m, s, cs)


def norm_hex(c, fallback=DEFAULT_ACCENT):
    c = str(c or "").strip().lstrip("#")
    return c.upper() if re.match(r"^[0-9a-fA-F]{6}$", c) else fallback


def hex_to_ass(c, alpha="00"):
    """#RRGGBB -> ASS 的 &HAABBGGRR"""
    c = norm_hex(c)
    return "&H%s%s%s%s&" % (alpha, c[4:6], c[2:4], c[0:2])


def filter_path(p):
    """写进 filter 字符串的路径：反斜杠换正斜杠，冒号要转义"""
    return os.path.abspath(p).replace("\\", "/").replace(":", "\\:")


def wrap_text(text, n):
    """按标点和字数折行（给封面用；字幕默认交给 libass 自动折）。"""
    text = re.sub(r"\s+", " ", str(text)).strip()
    if n <= 0 or len(text) <= n:
        return text
    punct = "，。！？；：、,.!?;: "
    lines, rest = [], text
    while len(rest) > n:
        window = rest[:n]
        idx = max([window.rfind(c) for c in punct] + [-1])
        cut = idx + 1 if idx >= n - 5 else n
        lines.append(rest[:cut].strip())
        rest = rest[cut:].lstrip()
    if rest.strip():
        lines.append(rest.strip())
    for i in range(1, len(lines)):
        while lines[i] and lines[i][0] in punct:
            lines[i - 1] += lines[i][0]
            lines[i] = lines[i][1:]
    # 最后一行剩得太短（孤字）就重排一次：优先在标点或「的 / 了」后面劈，
    # 那里断开读着最顺；实在没有就把两行对半劈（中文允许在任意两字之间换行）
    if len(lines) >= 2 and len(lines[-1]) <= max(2, n // 3):
        merged = lines[-2] + lines[-1]
        half = (len(merged) + 1) // 2
        spots = [i + 1 for i, ch in enumerate(merged)
                 if ch in punct + "的了" and i + 1 < len(merged)]
        cut = min(spots, key=lambda i: abs(i - half)) if spots else half
        lines[-2:] = [merged[:cut], merged[cut:]]
    return "\\N".join([x for x in lines if x])


def abs_from(p, base):
    if not p:
        return p
    return p if os.path.isabs(p) else os.path.normpath(os.path.join(base, p))


def resolve_path(p, *bases):
    """路径随便怎么写都认：绝对路径 / 相对 input\\ / 相对 GPT-SoVITS 根目录。
    依次试，哪个存在用哪个；都不存在就返回「相对 input\\」那个，报错时看着更直观。"""
    if not p:
        return p
    p = os.path.expandvars(os.path.expanduser(str(p).strip()))
    if os.path.isabs(p):
        return os.path.normpath(p)
    cands = []
    for b in bases:
        if not b:
            continue
        c = os.path.normpath(os.path.join(b, p))
        if c not in cands:
            cands.append(c)
    for c in cands:
        if os.path.exists(c):
            return c
    return cands[0] if cands else os.path.normpath(p)


def default_root():
    """没给 --root 时，默认用隔壁那个 GPT-SoVITS 整合包"""
    return BUNDLE_HINT if os.path.isdir(BUNDLE_HINT) else None


def apply_video_cfg(args):
    """script.json 里可以写一个 "video" 块来定画面，省得每次都敲命令行。
    命令行给了的参数优先，这里只补还空着的；路径都相对 script.json 所在的 input\\。"""
    p = getattr(args, "script", None)
    if p and p.lower().endswith((".txt", ".md")):
        p = os.path.join(os.path.dirname(p), "script.json")   # 台词写在 script.txt 里，配置还是 script.json
    p = p or os.path.join(IN_DIR, "script.json")
    if not p or not os.path.exists(p):
        return args
    try:
        cfg = load_json(p)
    except Exception as ex:
        warn("script.json 读不出来（%s），画面参数就当没写" % ex)
        return args
    th = theme_of({"theme": args.theme} if getattr(args, "theme", None) else cfg)
    args._theme = th
    if getattr(args, "accent", None) is None:
        args.accent = th["accent"]
    v = cfg.get("video")
    if not isinstance(v, dict):
        return args
    base = os.path.dirname(os.path.abspath(p))
    for key, dst in (("mode", "mode"), ("title", "title"), ("subtitle", "subtitle"),
                     ("cover", "cover"), ("bg", "bg"), ("circle", "circle"),
                     ("no_circle", "no_circle"), ("font", "font"),
                     ("sub_color", "sub_color"),
                     ("sub_size", "sub_size"), ("title_size", "title_size"),
                     ("who_size", "who_size"), ("who_y", "who_y"),
                     ("wrap", "wrap"), ("sub_margin", "sub_margin"),
                     ("scrim", "scrim"), ("accent", "accent"),
                     ("visual", "visual"), ("speaker_tag", "speaker_tag"),
                     ("show_name", "name"), ("progress", "progress"),
                     ("no_subs", "no_subs"), ("size", "size"), ("fps", "fps")):
        if key in v and getattr(args, dst, None) is None:
            val = v[key]
            if dst in ("accent", "font", "sub_color") and not str(val or "").strip():
                continue          # 空字符串 = 走默认（跟主题自动挑），不算覆盖
            if dst in ("cover", "bg", "circle") and val:
                val = resolve_path(str(val), base)
            setattr(args, dst, val)
    return args


def default_render_paths(args):
    """script.json 的 video 块 + input\\ 里放的图 / b-roll 素材都自动用上，不用每次写参数"""
    apply_video_cfg(args)

    def first(*names):
        for n in names:
            for ext in IMG_EXTS:
                c = os.path.join(IN_DIR, n + ext)
                if os.path.exists(c):
                    return c
        return None

    if not getattr(args, "cover", None):
        args.cover = first("cover")
    if not getattr(args, "bg", None):
        args.bg = first("bg", "background")
    if not getattr(args, "circle", None):
        args.circle = first("circle", "avatar")
    if not getattr(args, "broll", None):
        b = os.path.join(IN_DIR, "broll")
        if os.path.isdir(b) and any(f.lower().endswith(VIDEO_EXTS) for f in os.listdir(b)):
            args.broll = b
    return args


def print_getting_started():
    log(GETTING_STARTED)


def default_out_path(folder, kind, ext, stamp=None):
    """默认文件名带上日期时间：podcast_20261014_2106.mp4
    免得每跑一次就把上一次的成片覆盖掉（同一分钟里跑第二次再加个序号）。"""
    stamp = stamp or time.strftime("%Y%m%d_%H%M")
    p = os.path.join(folder, "%s_%s.%s" % (kind, stamp, ext))
    n = 2
    while os.path.exists(p):
        p = os.path.join(folder, "%s_%s_%d.%s" % (kind, stamp, n, ext))
        n += 1
    return p


# ---------------------------------------------------------------- ffmpeg
_CAPS = {}


def find_ffmpeg(explicit=None):
    cands = []
    if explicit:
        cands.append(explicit)
    if os.environ.get("PODCAST_FFMPEG"):
        cands.append(os.environ["PODCAST_FFMPEG"])
    here = os.path.dirname(os.path.abspath(__file__))
    cands.append(os.path.join(here, "ffmpeg.exe"))
    cands.append(os.path.join(os.path.dirname(here), "tools_aigc_GPT-SoVITS",
                              "GPT-SoVITS-v2pro-20250604", "runtime", "ffmpeg.exe"))
    cands += KNOWN_FFMPEG
    w = shutil.which("ffmpeg")
    if w:
        cands.append(w)
    found, seen = [], set()
    for c in cands:
        if not c:
            continue
        c = os.path.abspath(c)
        if c in seen or not os.path.exists(c):
            continue
        seen.add(c)
        found.append(c)
    if not found:
        die("找不到 ffmpeg。用 --ffmpeg 指一个，或者设 PODCAST_FFMPEG 环境变量。\n"
            "   提示：GPT-SoVITS 整合包里的 runtime\\ffmpeg.exe 没有 libx264（导不出通用 MP4）；\n"
            "   完整版可以用 D:\\Workspace\\AI\\win-pyvideotrans-v3.86\\ffmpeg\\ffmpeg.exe")
    for c in found:
        if probe_ffmpeg(c)["x264"]:
            return c
    warn("手上的 ffmpeg 都没有 libx264，只能导 VP9/WebM（网页/B站能放，抖音小红书不一定认）：%s"
         % found[0])
    return found[0]


def probe_ffmpeg(ff):
    if ff in _CAPS:
        return _CAPS[ff]
    if not os.path.exists(ff):
        die("ffmpeg 不存在: %s" % ff)
    enc = run([ff, "-hide_banner", "-encoders"], quiet=True).stdout or ""
    flt = run([ff, "-hide_banner", "-filters"], quiet=True).stdout or ""
    _CAPS[ff] = {
        "x264": "libx264" in enc,
        "ass": "libass" in flt,
        "showwaves": "showwaves" in flt,
        "showspectrum": "showspectrum" in flt,
        "loudnorm": "loudnorm" in flt,
    }
    return _CAPS[ff]


def find_ffprobe(ff):
    d = os.path.dirname(ff)
    for name in ("ffprobe.exe", "ffprobe"):
        p = os.path.join(d, name)
        if os.path.exists(p):
            return p
    return shutil.which("ffprobe")


def probe_duration(ff, path):
    fp = find_ffprobe(ff)
    if fp:
        p = run([fp, "-v", "error", "-show_entries", "format=duration",
                 "-of", "default=nw=1:nk=1", path], quiet=True, check=False)
        try:
            return float((p.stdout or "").strip())
        except Exception:
            pass
    try:
        import soundfile as sf
        return sf.info(path).duration
    except Exception:
        return None


# ---------------------------------------------------------------- 音频
def to_pcm_wav(ff, src, dst, sr=SR, af=None):
    """统一成 sr / 单声道 / pcm_s16le。所有片段都过这道，后面合并才省心。
    af 可以塞额外的 -af 滤镜（电平对齐就是用 volume= 走这里的）。"""
    os.makedirs(os.path.dirname(os.path.abspath(dst)), exist_ok=True)
    cmd = [ff, "-y", "-hide_banner", "-loglevel", "error", "-i", src, "-vn"]
    if af:
        cmd += ["-af", af]
    cmd += ["-ac", "1", "-ar", str(sr), "-c:a", "pcm_s16le", dst]
    run(cmd, quiet=True)
    return dst


def measure_loudness(ff, path):
    """量一句的响度：返回 (integrated LUFS, 峰值 dBFS)；量不出来给 None。
    用 ffmpeg 自带的 ebur128（就是广播行业那个响度标准），一次扫描拿到两个值。"""
    p = run([ff, "-hide_banner", "-nostats", "-i", path,
             "-af", "ebur128=peak=true", "-f", "null", "-"], quiet=True, check=False)
    txt = (p.stderr or "") + "\n" + (p.stdout or "")
    I = pk = None
    for m in re.finditer(r"I:\s*(-?\d+(?:\.\d+)?)\s*LUFS", txt):
        I = float(m.group(1))                     # 匹配多次，最后一个才是整段
    for m in re.finditer(r"Peak:\s*(-?\d+(?:\.\d+)?)\s*dBFS", txt):
        pk = float(m.group(1))
    if I is not None and not (-70.0 < I < 20.0):
        I = None
    return I, pk


def plan_level_gains(entries, ff, target):
    """按说话人算增益，返回 {说话人: 增益dB}。

    同一个人共用一条增益 —— 只把「人」对齐，不抹平句内起伏（该轻的句子还是轻）。
    响度用各句中位数（比平均值抗离群值），再按峰值留 1dB 余量防止削顶。"""
    import statistics
    per, peaks = {}, {}
    for e in entries:
        if not e.get("audio"):
            continue
        I, pk = measure_loudness(ff, e["audio"])
        if I is not None:
            per.setdefault(e["key"], []).append(I)
        if pk is not None:
            peaks.setdefault(e["key"], []).append(pk)
    gains = {}
    for k, vals in per.items():
        med = statistics.median(vals)
        g = target - med
        if peaks.get(k):
            g = min(g, -1.0 - max(peaks[k]))
        gains[k] = round(max(-24.0, min(24.0, g)), 2)
        log("[电平] %s：%d 句，响度中位数 %.1f LUFS -> 增益 %+.1f dB"
            % (k, len(vals), med, gains[k]))
    return gains


def merge_lines(items, out_path):
    """逐句拼成 master.wav，句间插 gap 静音；顺带把每句的起止时间算出来。"""
    import numpy as np
    import soundfile as sf
    parts, sr = [], None
    for i, e in enumerate(items):
        audio, sr0 = sf.read(e["wav"], dtype="float32", always_2d=True)
        if sr is None:
            sr = sr0
        if audio.shape[1] > 1:
            audio = audio.mean(axis=1, keepdims=True)
        if i:
            parts.append(np.zeros((int(round(e["gap"] * sr)), 1), dtype="float32"))
        e["start"] = sum(p.shape[0] for p in parts) / float(sr)
        e["duration"] = audio.shape[0] / float(sr)
        e["end"] = e["start"] + e["duration"]
        parts.append(audio)
    if not parts:
        die("一条音频都没有，合不出 master.wav")
    data = np.concatenate(parts, axis=0)
    os.makedirs(os.path.dirname(os.path.abspath(out_path)), exist_ok=True)
    sf.write(out_path, data, sr)
    return len(data) / float(sr)


def make_test_audio(ff, seconds, dst, freq=None):
    """demo 用：造一段有起伏的音频，只为看波形和版式，不是真语音

    lavfi 的 sine 源本身只有 -18dBFS 左右，所以这里要补一级音量，否则听着像没声音。
    """
    f = freq or random.choice([155, 180, 205, 232])
    src = "sine=frequency=%d:duration=%.3f" % (f, seconds)
    af = "tremolo=f=5.5:d=0.72,highpass=f=95,volume=5.5"
    run([ff, "-y", "-hide_banner", "-loglevel", "error", "-f", "lavfi", "-i", src,
         "-af", af, "-ac", "1", "-ar", str(SR), dst], quiet=True)
    return dst


# ---------------------------------------------------------------- 字幕 / 封面
def write_ass(path, tl, opt):
    W, H = opt["W"], opt["H"]
    palette, i = {}, 0
    for k, s in (tl.get("speakers") or {}).items():
        palette[k] = norm_hex(s.get("color"), spk_auto_color(i))
        i += 1
    if not palette:
        palette = {"A": DEFAULT_ACCENT}
    # 字号按「短边」算：竖屏 1080x1920 取 1080，横屏 1920x1080 取 810，两种都不会离谱
    base = min(W, int(H * 0.75))
    # 都能改：命令行 --sub-size / --title-size / --who-size，或 script.json 的 video.sub_size …
    sub_fs = int(opt.get("sub_size") or 0) or int(base * 0.065)
    title_fs = int(opt.get("title_size") or 0) or int(base * 0.050)
    who_fs = int(opt.get("who_size") or 0) or int(base * 0.072)
    who_y = float(opt.get("who_y") or 0.455)
    pad_h = int(base * 0.055)
    sub_mv = int(H * (opt.get("sub_margin") or 0.045))
    top_mv = int(opt.get("pb", 0)) + int(H * 0.030)
    font = opt.get("font") or pick_default_font()
    sub_fg = opt.get("sub_fg")          # 有值 = 所有字幕同一个颜色（最干净）；None = 按说话人上色
    head = [
        "[Script Info]",
        "ScriptType: v4.00+",
        "PlayResX: %d" % W,
        "PlayResY: %d" % H,
        "WrapStyle: 2",
        "ScaledBorderAndShadow: yes",
        "",
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
    ]
    body = []
    title_fg = hex_to_ass(sub_fg) if sub_fg else "&H00FFFFFF&"
    for k in sorted(palette):
        body.append("Style: S_%s,%s,%d,%s,&H000000FF,&H00101010,&H8C000000,-1,0,0,0,100,100,"
                    "1,0,1,4,0,2,%d,%d,%d,1"
                    % (k, font, sub_fs, hex_to_ass(sub_fg or palette[k]), pad_h, pad_h, sub_mv))
    body.append("Style: Title,%s,%d,%s,&H000000FF,&H00101010,&H8C000000,-1,0,0,0,100,"
                "100,1,0,1,3,0,8,%d,%d,%d,1"
                % (font, title_fs, title_fg, pad_h, pad_h, top_mv))
    body.append("Style: Tag,%s,%d,&H00FFFFFF,&H000000FF,&H00101010,&H8C000000,-1,0,0,0,100,"
                "100,1,0,1,3,0,7,%d,%d,%d,1"
                % (font, int(base * 0.034), pad_h, pad_h, top_mv))
    body.append("Style: Who,%s,%d,%s,&H000000FF,&H00101010,&H8C000000,-1,0,0,0,100,"
                "100,2,0,1,4,0,5,0,0,0,1"
                % (font, who_fs, title_fg))
    ev = ["", "[Events]",
          "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text"]
    dur = float(tl.get("duration") or 0.0)
    if opt.get("title"):
        head_line = r"{\fs%d}%s" % (title_fs, wrap_text(opt["title"], 12))
        if opt.get("subtitle"):
            head_line += r"\N{\fs%d\c%s}%s" % (int(title_fs * 0.62),
                                              hex_to_ass(opt["accent"]),
                                              wrap_text(opt["subtitle"], 20))
        ev.append("Dialogue: 0,%s,%s,Title,,0,0,0,,%s"
                  % (ass_time(0), ass_time(dur), head_line))
    wrap_n = int(opt.get("wrap") or 0) or max(6, int((W - 2 * pad_h) / float(sub_fs)))
    for ln in tl.get("lines") or []:
        k = ln.get("speaker") or "A"
        sty = "S_%s" % (k if k in palette else sorted(palette)[0])
        col = hex_to_ass(palette.get(k, palette[sorted(palette)[0]]))
        text = wrap_text(ln.get("text", ""), wrap_n)
        if opt.get("show_name", True):
            text = "{\\c%s}%s：{\\c%s}%s" % (col, ln.get("name") or k, title_fg, text)
        ev.append("Dialogue: 0,%s,%s,%s,,0,0,0,,%s"
                  % (ass_time(ln.get("start", 0)), ass_time(ln.get("end", 0)), sty, text))
        who_name = re.sub(r"[:：\s]+$", "", str(ln.get("name") or k))   # 画面上的名字不带尾巴上的冒号
        if opt.get("who", True):
            ev.append("Dialogue: 0,%s,%s,Who,,0,0,0,,{\\an5\\pos(%d,%d)\\c%s}%s"
                      % (ass_time(ln.get("start", 0)), ass_time(ln.get("end", 0)),
                         W // 2, int(H * who_y), col, who_name))
        if opt.get("speaker_tag"):
            ev.append("Dialogue: 0,%s,%s,Tag,,0,0,0,,{\\c%s}%s"
                      % (ass_time(ln.get("start", 0)), ass_time(ln.get("end", 0)), col,
                         who_name))
    with open(path, "w", encoding="utf-8") as f:
        f.write("\n".join(head + body + ev) + "\n")
    return path


def theme_of(cfg, fallback=None):
    """把 script.json（或它的 video 块）里的 "theme" 解析成主题字典。
    名字写错只警告，不中断。"""
    name = None
    if isinstance(cfg, dict):
        name = cfg.get("theme")
        v = cfg.get("video")
        if not name and isinstance(v, dict):
            name = v.get("theme")
    key = str(name or fallback or DEFAULT_THEME).strip().lower()
    if key not in THEMES:
        warn("不认识的配色主题 %r，用默认的 %s（可选：%s）"
             % (name, fallback or DEFAULT_THEME, " / ".join(sorted(THEMES))))
        key = fallback or DEFAULT_THEME
    t = dict(THEMES[key])
    t["name"] = key
    return t


def spk_auto_color(n):
    """没在 script.json 里指定颜色时，按当前主题自动取色"""
    cs = (_ACTIVE_THEME or THEMES[DEFAULT_THEME])["colors"]
    return cs[n % len(cs)]


_FONT_SET = "__unset__"


def installed_fonts():
    """本机装了哪些字体（读注册表）；读不到返回 None，表示「不知道」"""
    global _FONT_SET
    if _FONT_SET == "__unset__":
        names = set()
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE,
                                r"SOFTWARE\Microsoft\Windows NT\CurrentVersion\Fonts") as k:
                i = 0
                while True:
                    try:
                        v, _, _ = winreg.EnumValue(k, i)
                    except OSError:
                        break
                    names.add(re.sub(r"\s*\((TrueType|OpenType|All res)\)\s*$", "", v).strip().lower())
                    i += 1
        except Exception:
            names = None
        _FONT_SET = names
    return _FONT_SET


def pick_default_font():
    """从 FONT_PREFS 里挑第一个本机装了的；一个都认不出就退到微软雅黑"""
    have = installed_fonts()
    if have:
        for f in FONT_PREFS:
            fl = f.lower()
            if any(n == fl or n.startswith(fl) for n in have):
                return f
    return "Microsoft YaHei"


def pick_font_path():
    for p in FONT_CANDIDATES:
        if os.path.exists(p):
            return p
    return None


def make_cover(path, W, H, accent, bg=None, circle=None, no_circle=False):
    """没给封面就自动画一张：深色渐变（或你给的背景图）+ 中间一个圆

    标题 / 副标题 / 说话人名字都不画进这张图，它们由 subs.ass 叠在上面
    （所以改标题不用重新出图，换说话人名字也能跟着变）。中间那个圆的三种情况：
      circle 给了图 -> 圆里放这张图（自动裁圆，外面再描一圈主题色）
      没给图        -> 画原来的同心圆
      no_circle     -> 什么都不画
    """
    from PIL import Image, ImageChops, ImageDraw
    resample = getattr(getattr(Image, "Resampling", Image), "LANCZOS")
    rgb = tuple(int(norm_hex(accent)[i:i + 2], 16) for i in (0, 2, 4))
    cx = int(W * 0.5)
    R = int(min(W * 0.17, H * 0.20))               # 横屏时别把圆撑得太大
    cy = max(int(H * 0.26), R + int(H * 0.13))     # 也别顶到上面的标题
    if bg:
        im = Image.open(bg).convert("RGB")
        s = max(W / float(im.width), H / float(im.height))
        im = im.resize((max(1, int(im.width * s)), max(1, int(im.height * s))),
                       resample)
        x, y = (im.width - W) // 2, (im.height - H) // 2
        base = im.crop((x, y, x + W, y + H))
        base = Image.blend(base, Image.new("RGB", (W, H), (4, 6, 10)), 0.42)
    else:
        # 一整片「墨色」竖直渐变：上面稍亮、越往下越沉，中间没有接缝
        # （旧版在 0.42H 处换了一次渐变，放大看是一道横杠）
        base = Image.new("RGB", (W, H), (12, 14, 20))
        d0 = ImageDraw.Draw(base)
        top, bot = (18, 20, 28), (5, 6, 10)
        for y in range(H):
            t = (y / float(H - 1)) ** 0.85
            d0.line([(0, y), (W, y)],
                    fill=tuple(int(top[i] + (bot[i] - top[i]) * t) for i in range(3)))
        # 圆后面再加一层很淡的暖光晕：低分辨率画完再放大，天然平滑
        gw = 54
        gh = max(1, int(round(gw * H / float(W))))
        glow = Image.new("RGB", (gw, gh), (0, 0, 0))
        gd = ImageDraw.Draw(glow)
        gcx, gcy = cx * gw / float(W), cy * gh / float(H)
        gr = R * 3.4 * gw / float(W)
        for i in range(30, 0, -1):
            rr = gr * i / 30.0
            k = (1 - i / 30.0) ** 2.2
            gd.ellipse([gcx - rr, gcy - rr, gcx + rr, gcy + rr],
                       fill=tuple(int(c * 0.20 * k) for c in rgb))
        base = ImageChops.add(base, glow.resize((W, H), resample))
    d = ImageDraw.Draw(base)
    d.rectangle([0, 0, W, max(2, int(H * 0.006))], fill=rgb)
    if no_circle:
        pass
    elif circle:
        im = Image.open(circle).convert("RGB")
        side = min(im.width, im.height)
        ox, oy = (im.width - side) // 2, (im.height - side) // 2
        im = im.crop((ox, oy, ox + side, oy + side)).resize((2 * R, 2 * R), resample)
        mask = Image.new("L", (2 * R, 2 * R), 0)
        ImageDraw.Draw(mask).ellipse([0, 0, 2 * R - 1, 2 * R - 1], fill=255)
        base.paste(im, (cx - R, cy - R), mask)
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=rgb, width=max(3, int(W * 0.008)))
    else:
        d.ellipse([cx - R, cy - R, cx + R, cy + R], outline=rgb, width=max(3, int(W * 0.006)))
        for k in range(3):
            rr = int(R * (0.42 + 0.22 * k))
            d.ellipse([cx - rr, cy - rr, cx + rr, cy + rr], outline=rgb, width=2)
    base.save(path)
    return path


# ---------------------------------------------------------------- synth
def normalize_speakers(script, args, base, root=None):
    global _ACTIVE_THEME
    _ACTIVE_THEME = theme_of({"theme": args.theme} if getattr(args, "theme", None) else script)
    th = _ACTIVE_THEME
    spks = script.get("speakers") or {}
    if not spks:
        spks = {"A": {}}
    out = {}
    for i, (k, v) in enumerate(spks.items()):
        v = dict(v or {})
        tts = dict(v.get("tts") or {})
        for fld in ("ref", "ref_text", "ref_lang", "lang", "gpt", "sovits", "cut",
                    "speed", "temperature", "top_k", "top_p", "seed",
                    "engine", "voice", "rate", "volume", "pitch",
                    "api_key", "base_url", "model"):
            if fld in v and fld not in tts:
                tts[fld] = v[fld]
        for fld in ("ref", "ref_text", "gpt", "sovits"):
            if not tts.get(fld) and getattr(args, fld, None):
                tts[fld] = getattr(args, fld)
        # --ai-engine / --ai-voice / --ai-model … 的覆盖规则：
        #   一给 --ai-engine，所有「不是你」的人整体换成这个在线引擎；
        #   只给 --ai-voice / --ai-model 的话，只对本来就走现成引擎的人生效，
        #   不会把你本机 GPT-SoVITS 那条路带跑偏。
        # --ai-speaker（默认 A）里列出来的是「我自己」，永远不动。
        mine = [s.strip() for s in str(getattr(args, "ai_speaker", "") or "A").split(",")]
        mine = [s for s in mine if s]
        if k not in mine:
            raw = getattr(args, "ai_engine", None)
            forced = ENGINE_ALIAS_OF.get(str(raw).strip().lower()) if raw else None
            if raw and not forced:
                die("不认识的 --ai-engine: %r（支持 google / baidu / openai / edge / sapi）" % raw)
            online = forced or ENGINE_ALIAS_OF.get(str(tts.get("engine") or "").strip().lower())
            if online in AI_LIKE_ENGINES:
                if forced:
                    tts["engine"] = raw
                for src, dst in (("ai_voice", "voice"), ("ai_key", "api_key"),
                                 ("ai_base", "base_url"), ("ai_model", "model")):
                    val = getattr(args, src, None)
                    if val:
                        tts[dst] = val
        if tts.get("ref"):
            tts["ref"] = resolve_path(tts["ref"], base, root)
        out[k] = {"key": k, "name": v.get("name") or k,
                  "color": norm_hex(v.get("color"), th["colors"][i % len(th["colors"])]),
                  "tts": tts}
    return out


# --------------------------------------------- 台词脚本 script.txt（A: / B: 分块）
_TOKEN_RE = re.compile(r"^[A-Za-z0-9_\u4e00-\u9fff]{1,4}$")
_ASCII_NAME_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]{0,3}$")
_END_PUNCT = "。！？!?；;…"
_CLOSERS = "\u201d\u2019\u300d\u300f\u300b\u3009\uff09\u3011"    # ” ’ 」 』 》 〉 ） 】
MINI_CHARS = 8            # 短于这么多字的碎片并回上一句


def _split_speaker_tag(line):
    """把 'A: 台词' 拆成 ('A', '台词')；不像说话人标签就返回 (None, 原行)。"""
    idx = -1
    for i, ch in enumerate(line):
        if ch in ":：":
            idx = i
            break
    if idx <= 0:
        return None, line
    token = line[:idx].strip()
    if not _TOKEN_RE.match(token):
        return None, line
    return token, line[idx + 1:].strip()


def _is_speaker_tag(token, rest, spks):
    """token 算不算说话人？已经在 speakers 里的当然算；'A' / 'S1' 这种英文名直接算；
    中文名（'小明：'）只在后面没跟内容时才认，免得把『注意：xxx』当成换人。"""
    if token in spks:
        return True
    if _ASCII_NAME_RE.match(token):
        return True
    return rest == ""


def _join_lines(lines):
    """把一个说话人的多行正文接成一段。中文直接接，英文单词之间补个空格。"""
    out = ""
    for raw in lines:
        s = raw.strip()
        if not s:
            continue
        if out and out[-1].isascii() and out[-1].isalnum() and s[0].isascii() and s[0].isalnum():
            out += " "
        out += s
    return out


def split_sentences(text):
    """按句末标点切句。句尾标点后面紧跟的引号一起收走，
    所以『…他就成了有灵的活人。”』不会被从引号里切断。"""
    out, buf = [], ""
    i, n = 0, len(text)
    while i < n:
        ch = text[i]
        buf += ch
        i += 1
        if ch in _END_PUNCT:
            while i < n and (text[i] in _END_PUNCT or text[i] in _CLOSERS):
                buf += text[i]
                i += 1
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return [s.strip() for s in out if s.strip()]


def merge_short(parts, mini=MINI_CHARS):
    """太短的一句（比如独立成句的一个『好。』）并回相邻那句，念起来更自然。"""
    out = []
    for s in parts:
        if out and len(out[-1]) < mini:
            out[-1] += s
        else:
            out.append(s)
    if len(out) >= 2 and len(out[0]) < mini:
        out = [out[0] + out[1]] + out[2:]
    return out


# ------------------------------------------------- 吞字防守（合成后自查时长）
CLAUSE_PUNCT = "，,、；;：:"     # 合成小口的切点；GPT-SoVITS 内部也是按这些切的
CJK_PER_SEC = 5.0               # 实测：这个音色约 5 个字/秒
LATIN_PER_SEC = 13.0            # 英文大约 13 个字母/秒
TAIL_PAUSE = 0.3                # GPT-SoVITS 每段尾巴会垫约 0.3 秒静音
TAIL_TRIM = 0.25                # 我们自己切小口后，只留这么点尾音当逗号停顿
SHORT_RATIO = 0.6               # 实际时长不到「该有时长」的 60% 就算被吞了
LONG_RATIO = 2.5                # 反过来，超过「该有时长」这么多倍也算这一遍没念好
AI_REL_TRIM = 25.0              # 在线引擎那句里，比最响处低这么多 dB 的当底噪切掉
AI_TRIM_FLOOR = -55.0           # 但也不低于这个绝对值，免得安静的一句话被整段切没
AI_JUNK_DB = 12.0               # 真空外侧那截比内侧话音低这么多 dB，才算垃圾（不是换气）
AI_QUIET_DB = -70.0             # 一帧的峰值低于这个就当「静音」（mp3 解码出来的静音是 -95dB
                                # 而不是精确 0，阈值卡太死会认不出来；真人声最轻的帧也在 -60dB 以上）


def expected_seconds(text, speed=1.0):
    """这句大概该念多少秒。用来发现「明明这么长的台词，音频却很短」= 吞字。"""
    cjk = sum(1 for ch in text if "\u4e00" <= ch <= "\u9fff")
    latin = sum(1 for ch in text if ch.isascii() and ch.isalnum())
    return max(0.8, (cjk / CJK_PER_SEC + latin / LATIN_PER_SEC) / max(0.1, speed) + TAIL_PAUSE)


def trim_silence(wav, sr, tail_keep=TAIL_TRIM, floor_db=-45.0):
    """掐掉一小口头尾的静音，再补回一小段尾巴。
    GPT-SoVITS 每段尾巴垫约 0.44 秒，不掐的话逗号听着像句号。"""
    import numpy as np
    x = np.asarray(wav)
    if x.ndim > 1:
        x = x.reshape(-1)
    if x.size == 0:
        return x
    thresh = (10.0 ** (floor_db / 20.0)) * 32767.0
    idx = np.nonzero(np.abs(x.astype(np.float32)) > thresh)[0]
    if idx.size == 0:
        return x
    return x[int(idx[0]):min(x.size, int(idx[-1]) + 1 + int(round(tail_keep * sr)))]


def split_clauses(text):
    """把一句切成小口（逗号一层）。切这么细才能逐口检查有没有被吞。"""
    out, buf = [], ""
    for ch in text:
        buf += ch
        if ch in CLAUSE_PUNCT:
            out.append(buf)
            buf = ""
    if buf.strip():
        out.append(buf)
    return [s.strip() for s in out if s.strip()]


def trim_head_noise(wav, sr, rel_db=AI_REL_TRIM, floor_db=AI_TRIM_FLOOR,
                    frame=0.02, smooth=0.1, tail_keep=TAIL_TRIM,
                    scan=3.0, gap_min=0.15):
    """掐掉一句开头/结尾的底噪、气口，以及中间那种 -99dB 的数字静音。

    在线引擎（硅基的 MOSS-TTSD 这类）爱在这句话前面吐两三秒「滋滋」底噪，
    比正文低 20~30dB、但又不是静音 —— 听着就像多念了一个字，也会把整句撑长。
    两道判据一起用：

      1) 相对音量：比本句最响处低 rel_db 的一律算底噪（不看绝对音量，
         所以整体很轻的一句也不会被切没）；
      2) 数字真空：开头/结尾 scan 秒内出现 >= gap_min 秒的「纯静音」，
         而且真空**外侧**那截明显比内侧话音轻 >= AI_JUNK_DB，就一起切掉 ——
         在线引擎的底噪后面常跟着这样一段真空，底噪只比人声低 20dB 时
         靠这条也能认出来。加「外侧更轻」这个前提，是为了不动真正的话：
         句子里正常的换气停顿（两侧一样响）不会被当成垃圾切掉。

    另外，结尾那一整段静音（>= gap_min 秒）也直接切掉，句间停顿交给 gap 去管。
    真正的话音一个字不动：字头还会往前留 20ms，别把爆破音削掉。"""
    import numpy as np
    x = np.asarray(wav).reshape(-1).astype(np.float32)
    n = max(1, int(round(frame * sr)))
    nfr = int(x.size // n)
    if nfr < 4:
        return x
    frames = x[:nfr * n].reshape(nfr, n)
    rms = np.sqrt((frames ** 2).mean(axis=1))
    k = max(1, int(round(smooth / frame)))
    env = np.convolve(rms, np.ones(k, dtype=np.float32) / k, mode="same")
    top = float(np.percentile(env, 99.0))          # 用 99 分位而不是最大值，抗一个爆点
    if top <= 0:
        return x
    envdb = 20 * np.log10(np.maximum(env, 1e-9))
    thr = max(20 * np.log10(top) - rel_db, floor_db)
    loud = envdb > thr
    if not loud.any():
        return x
    first = int(np.argmax(loud))
    last = nfr - 1 - int(np.argmax(loud[::-1]))
    lim = min(nfr, int(round(scan / frame)))
    need = max(1, int(round(gap_min / frame)))
    quiet = np.abs(frames).max(axis=1) < 10.0 ** (AI_QUIET_DB / 20.0)   # 这一帧是静音
    j = nfr - 1
    while j >= 0 and quiet[j]:      # 结尾那一整段静音直接切掉：句间停顿由 gap 管，
        j -= 1                      # 留着只会让这一句听起来拖沓
    if nfr - 1 - j >= need:
        last = min(last, j)
    head_gap = tail_gap = None
    run = 0
    for i in range(lim):                            # 开头的真空：切到它结束为止
        run = run + 1 if quiet[i] else 0
        if run >= need:
            j = i
            while j + 1 < nfr and quiet[j + 1]:
                j += 1
            head_gap = (i - run + 1, j)
            break
    run = 0
    for i in range(nfr - 1, max(-1, nfr - lim - 1), -1):   # 结尾的真空：从它开始切
        run = run + 1 if quiet[i] else 0
        if run >= need:
            j = i
            while j - 1 >= 0 and quiet[j - 1]:
                j -= 1
            tail_gap = (j, i + run - 1)
            break
    weaker = 10.0 ** (-AI_JUNK_DB / 20.0)
    if head_gap:
        pre, post = frames[:head_gap[0]], frames[head_gap[1] + 1:]
        pre_pk = float(np.abs(pre).max()) if pre.size else 0.0
        post_pk = float(np.abs(post).max()) if post.size else 0.0
        # 外侧比内侧轻 12dB 以上，而且外侧连一帧「像样的话音」都没有 -> 才是垃圾。
        # 后一个条件是为了护住「轻声开头 + 停顿 + 大声正文」这种念法。
        if pre_pk < post_pk * weaker and not loud[:head_gap[0]].any():
            first = max(first, head_gap[1] + 1)
    if tail_gap:
        pre, post = frames[:tail_gap[0]], frames[tail_gap[1] + 1:]
        pre_pk = float(np.abs(pre).max()) if pre.size else 0.0
        post_pk = float(np.abs(post).max()) if post.size else 0.0
        if post_pk < pre_pk * weaker and not loud[tail_gap[1] + 1:].any():
            last = min(last, tail_gap[0] - 1)
    a = max(0, first * n - int(round(0.02 * sr)))  # 字头往前留 20ms，别把爆破音削掉
    b = min(x.size, (last + 1) * n + int(round(tail_keep * sr)))
    return x[a:b] if b - a >= nfr * n // 4 else x


def parse_script_txt(path, spks, gap0, mini=MINI_CHARS):
    """读 script.txt：『A:』『B:』分块，一个块里想写几行写几行，一行里几句都行。

    每个说话人的正文先接成一段，再按标点切成一句一句 —— 换行纯粹为了方便你边写边改，
    不影响断句。解析结果和 script.json 的 lines 完全同构（index/key/text/audio/gap），
    后面合成、拼时间轴的代码一行都不用动。
    """
    with open(path, encoding="utf-8-sig") as f:
        raw = f.read()
    entries = []
    cur = [None, []]                     # [当前说话人, 这个人的正文行]

    def flush():
        key, buf = cur
        if not key:
            return
        text = _join_lines(buf)
        if not text:
            return
        for s in merge_short(split_sentences(text), mini):
            entries.append({"index": len(entries) + 1, "key": key, "text": s,
                            "audio": None, "gap": gap0})

    for ln, line in enumerate(raw.splitlines(), 1):
        s = line.strip()
        if not s:
            continue
        token, rest = _split_speaker_tag(s)
        if token and _is_speaker_tag(token, rest, spks):
            flush()
            cur[0], cur[1] = token, ([rest] if rest else [])
            if token not in spks:
                spks[token] = {"key": token, "name": token,
                               "color": spk_auto_color(len(spks)), "tts": {}}
            continue
        if cur[0] is None:
            die("%s 第 %d 行还没标说话人就开始写台词了：%s\n"
                "   台词前先单独来一行『A:』『B:』，标一下这句是谁说的。"
                % (os.path.basename(path), ln, s))
        cur[1].append(s)
    flush()
    if not entries:
        die("%s 里没解析出台词。格式是：先一行『A:』，下面写 A 说的话。" % os.path.basename(path))
    return entries


def entries_from_lines(raw_lines, spks, gap0, base, root):
    """老的 script.json 写法：lines 里一条一句（继续支持，向后兼容）。"""
    if isinstance(raw_lines, str):
        raw_lines = [{"speaker": "A", "text": t} for t in raw_lines.splitlines() if t.strip()]
    if not raw_lines:
        die("script.json 里没有 lines（台词也可以单独写在 script.txt 里，见 README 第二节）")
    entries = []
    for i, ln in enumerate(raw_lines, 1):
        if not isinstance(ln, dict):
            die("lines 第 %d 条不是对象，应该长这样：{\"speaker\":\"A\",\"text\":\"...\"}" % i)
        key = str(ln.get("speaker") or "A")
        if key not in spks:
            spks[key] = {"key": key, "name": key,
                         "color": spk_auto_color(len(spks)), "tts": {}}
        entries.append({"index": i, "key": key, "text": (ln.get("text") or "").strip(),
                        "audio": resolve_path(ln.get("audio"), base, root) if ln.get("audio") else None,
                        "gap": float(ln.get("gap_after", gap0))})
    return entries


def sweep_lines_dir(lines_dir, entries):
    """清掉上一版脚本剩下的逐句音频，只留这一版时间轴真的会用到的那些。

    脚本是「只覆盖、不清理」：改了台词再跑，上一版的 003_B.wav、010_B.wav
    会一直躺在 lines\\ 里，回头复听/排查问题根本分不清哪句是哪一版的。"""
    keep = set()
    for e in entries:
        keep.add("%04d_%s.wav" % (e["index"], e["key"]))
        if e.get("audio"):
            keep.add(os.path.basename(e["audio"]))
    gone = 0
    for f in os.listdir(lines_dir):
        if f in keep or not re.match(r"^(\d{4}_|\.raw_)", f):
            continue
        if os.path.splitext(f)[1].lower() not in AUDIO_EXTS:
            continue
        try:
            os.remove(os.path.join(lines_dir, f))
            gone += 1
        except OSError:
            pass
    if gone:
        log("[清理] 删掉 %d 个上一版剩下的逐句音频" % gone)


def load_tts_engine(root, version, cpu, half):
    if cpu:
        os.environ["CUDA_VISIBLE_DEVICES"] = ""
    os.environ["version"] = version
    if cpu:
        os.environ["is_half"] = "False"
    elif half:
        os.environ["is_half"] = "True"
    for sub in ["", "GPT_SoVITS/BigVGAN", "tools", "tools/asr", "GPT_SoVITS", "tools/uvr5"]:
        p = os.path.join(root, sub)
        if os.path.isdir(p) and p not in sys.path:
            sys.path.append(p)
    os.chdir(root)
    try:
        import onnxruntime as _ort
        # 这台机器没显卡，onnxruntime 每次还是会去找一遍 CUDA 库，然后在日志里刷一条
        # ONNXRuntimeError ... LoadLibrary failed with error 1114。纯噪音，跟合成没关系，压掉。
        _ort.set_default_logger_severity(4)
    except Exception:
        pass
    try:
        import GPT_SoVITS.inference_webui as iw
        from GPT_SoVITS.inference_webui import (change_gpt_weights, change_sovits_weights,
                                                get_tts_wav)
    except Exception as e:
        die("导入 GPT-SoVITS 推理代码失败：%r\n"
            "   确认 --root 是仓库根目录，并且已经 conda activate GPTSoVits" % (e,))
    try:
        # GPT-SoVITS 自己的 GPT_SoVITS/text/g2pw/onnx_api.py 在 import 时会把日志级别
        # 改回 3(error)，上面那次压制就被它顶掉了 —— 所以 import 完必须再压一次，
        # 不然那条 onnxruntime CUDA LoadLibrary 的噪音又会冒出来。
        import onnxruntime as _ort_again
        _ort_again.set_default_logger_severity(4)
    except Exception:
        pass
    return iw, change_gpt_weights, change_sovits_weights, get_tts_wav


def newest(d, ext):
    if not os.path.isdir(d):
        return None
    fs = [os.path.join(d, f) for f in os.listdir(d) if f.lower().endswith(ext)]
    return max(fs, key=os.path.getmtime) if fs else None


# ---------------------------------- 现成的配音：在线音色用的 HTTP 小工具
def _looks_audio(body, ctype):
    c = (ctype or "").lower()
    if any(k in c for k in ("audio", "mpeg", "octet-stream", "wav", "ogg")):
        return True
    # 有的服务端不回 Content-Type，那就看文件头：ID3 / MPEG 帧同步
    return len(body) > 1500 and (body[:3] == b"ID3" or body[:1] == b"\xff")


def ai_http(url, params=None, headers=None, data=None, timeout=120, expect_audio=True):
    """极简 HTTP 客户端。只用标准库，省得 podcast.py 多出 requests 这种依赖。"""
    import urllib.error
    import urllib.parse
    import urllib.request
    if params:
        url = url + ("&" if "?" in url else "?") + urllib.parse.urlencode(params)
    hdrs = {"User-Agent": AI_UA}
    hdrs.update(headers or {})
    req = urllib.request.Request(url, data=data, headers=hdrs,
                                 method="POST" if data is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            body = resp.read()
            ctype = resp.headers.get("Content-Type", "") or ""
    except urllib.error.HTTPError as ex:
        detail = ex.read()[:300].decode("utf-8", "replace").replace("\n", " ")
        raise RuntimeError("HTTP %s %s" % (ex.code, detail.strip()))
    except Exception as ex:
        raise RuntimeError("%r" % (ex,))
    if expect_audio and not _looks_audio(body, ctype):
        snippet = body[:200].decode("utf-8", "replace").replace("\n", " ").strip()
        raise RuntimeError("返回的不是音频（Content-Type: %s）：%s" % (ctype or "空", snippet))
    return body


def ai_chunks(text, limit):
    """在线接口一次喂不了太长的文本，按标点切成 <= limit 字的片段。"""
    text = text.strip()
    if len(text) <= limit:
        return [text]
    parts, cur = [], ""
    for ch in text:
        cur += ch
        if len(cur) >= limit and ch in "。！？；!?;，,、":
            parts.append(cur)
            cur = ""
    if cur:
        parts.append(cur)
    out = []
    for p in parts:                                   # 万一还是超长，硬切
        while len(p) > limit:
            out.append(p[:limit])
            p = p[limit:]
        if p:
            out.append(p)
    return out


def ai_join(fn, text, limit, out_path):
    """把切好的片段逐段请求，再首尾拼成一个 mp3（mp3 直接接字节就能播）。"""
    with open(out_path, "wb") as f:
        for piece in ai_chunks(text, limit):
            f.write(fn(piece))
    return out_path


def ai_google(tts, text, out_path):
    """谷歌翻译网页那个朗读口：免费、不用 key，中文只有一个女声，但很稳。"""
    lang = str(tts.get("voice") or "zh-CN")
    return ai_join(lambda q: ai_http(
        "https://translate.google.com/translate_tts",
        params={"ie": "UTF-8", "q": q, "tl": lang, "client": "tw-ob"},
        headers={"Referer": "https://translate.google.com/"}), text, 180, out_path)


def ai_baidu(tts, text, out_path):
    """百度翻译的朗读口：国内直连、免费、不用 key。spd 1~15 越大越快。"""
    try:
        spd = int(float(str(tts.get("speed", 5))))
    except (TypeError, ValueError):
        spd = 5
    per = str(tts.get("voice") or "0")
    return ai_join(lambda q: ai_http(
        "https://fanyi.baidu.com/gettts",
        params={"lan": "zh", "text": q, "spd": min(15, max(1, spd)),
                "source": "web", "per": per},
        headers={"Referer": "https://fanyi.baidu.com/"}), text, 180, out_path)


def ai_openai(tts, text, out_path, args):
    """任何 OpenAI 兼容的 /v1/audio/speech：硅基流动 / 智谱 / 火山方舟 / OpenAI / 本地服务都能接。"""
    import json as _json
    key = (tts.get("api_key") or os.environ.get("PODCAST_TTS_KEY") or "").strip()
    if not key:
        die("engine=openai 还得给个 API key，三种给法挑一个：\n"
            "   1) input\\script.json 的 speakers.B 里加一行 \"api_key\": \"sk-xxxx\"\n"
            "   2) 设一个环境变量 PODCAST_TTS_KEY\n"
            "   3) 命令行加 --ai-key sk-xxxx")
    model = (tts.get("model") or AI_MODEL).strip()
    voice = (tts.get("voice") or AI_VOICE).strip()
    payload = {"model": model, "input": text, "response_format": "mp3"}
    if tts.get("speed"):
        payload["speed"] = float(tts["speed"])
    # 硅基流动要求音色写成「模型名:音色」（FunAudioLLM/CosyVoice2-0.5B:anna），
    # 别的家（OpenAI / 智谱 / 火山）又只要光秃秃的音色名。
    # 所以先按你写的原样试一次，不行再自动补上模型前缀 —— 两种写法都认。
    tries = [voice]
    if "/" in model and ":" not in voice:
        tries.append("%s:%s" % (model, voice))
    last = None
    for i, v in enumerate(tries):
        try:
            audio = ai_http(tts.get("base_url") or AI_BASE,
                            headers={"Content-Type": "application/json",
                                     "Authorization": "Bearer " + key},
                            data=_json.dumps(dict(payload, voice=v),
                                             ensure_ascii=False).encode("utf-8"))
        except Exception as ex:
            last = ex
            continue
        if i and not OPENAI_VOICE_NOTE["shown"]:
            OPENAI_VOICE_NOTE["shown"] = True
            log("  （音色自动补成了 %s；想省这一次往返，就把 voice 直接写成这一整串）" % v)
        with open(out_path, "wb") as f:
            f.write(audio)
        return out_path
    raise last


AI_TIPS = {
    "google": "   google 走的是 translate.google.com 那个朗读口，得能连上谷歌；\n"
              "   连不上就换 --ai-engine baidu（国内直连，也是免费不用 key）。",
    "baidu": "   百度这个口子会限流，等一会儿再试；要还是不行，把上面的 HTTP 码发我。",
    "openai": "   先单独试一句：podcast_video.bat sample -e openai -v <音色>；\n"
              "   401/403 是 key 不对，400 一般是模型名或音色名不对，404 是接口地址不对。",
}


# --------------------------------------------------- 现成的 AI 配音（B 这种角色）
ENGINE_ALIASES = {
    "gsv": ("gsv", "gpt-sovits", "gpt_sovits", "local", "tts", ""),
    "google": ("google", "gtts", "google-tts", "googletts", "translate"),
    "baidu": ("baidu", "baidu-tts", "baidutts", "fanyi"),
    "openai": ("openai", "openai-tts", "compatible", "api", "siliconflow", "sf",
               "modelscope", "ark", "volcengine", "zhipu", "dashscope"),
    "edge": ("edge", "edge-tts", "edge_tts", "edgetts", "microsoft", "ms"),
    "sapi": ("sapi", "windows", "win", "offline"),
}
ENGINE_ALIAS_OF = {a: e for e, al in ENGINE_ALIASES.items() for a in al}        # 别名 -> 正名
AI_LIKE_ENGINES = ("google", "baidu", "openai", "edge", "sapi")                # 不用本机 GPT-SoVITS


def tts_engine(tts):
    """这个说话人用哪个引擎：
       gsv    = 本机 GPT-SoVITS 合成（默认，要 ref/权重）
       google = 谷歌翻译的朗读口（免费、不用 key、不用注册，要能连上谷歌）
       baidu  = 百度翻译的朗读口（免费、不用 key、不用注册，国内直连）
       openai = 任何 OpenAI 兼容的 /v1/audio/speech（硅基流动 / 智谱 / 火山方舟 …，
                要一个免费注册拿到的 key，音色比上面两个专业）
       edge   = 微软 edge-tts 神经网络音色（音色库最全，但这台机器的网络会被微软 403）
       sapi   = Windows 自带离线声音（Kangkang/Yaoyao/Huihui，机器人味，但不用网）"""
    e = str((tts or {}).get("engine") or "gsv").strip().lower()
    got = ENGINE_ALIAS_OF.get(e)
    if got:
        return got
    die("不认识的 engine: %r（支持 gsv / google / baidu / openai / edge / sapi）" % e)


def _synth_ai_raw(engine, tts, entry, lines_dir, args, ff):
    """用现成的 AI 配音合成一句，返回原始音频路径（后面统一转码）"""
    text = (entry.get("text") or "").strip()
    if not text:
        die("第 %d 句没有文本，配不了音" % entry["index"])
    stem = os.path.join(lines_dir, ".raw_ai_%04d" % entry["index"])

    if engine in AI_ENGINES:
        raw = stem + ".mp3"
        if os.path.exists(raw):
            os.remove(raw)
        try:
            if engine == "google":
                ai_google(tts, text, raw)
            elif engine == "baidu":
                ai_baidu(tts, text, raw)
            else:
                ai_openai(tts, text, raw, args)
        except Exception as ex:
            die("engine=%s 合成第 %d 句失败：%s\n%s"
                % (engine, entry["index"], ex, AI_TIPS.get(engine, "")))
        if not os.path.exists(raw) or os.path.getsize(raw) == 0:
            die("engine=%s 没写出音频（第 %d 句）：换个 --ai-voice，或者检查一下网络"
                % (engine, entry["index"]))
        return raw

    if engine == "edge":
        vdir = os.path.join(HERE, "_vendor")          # 打包进来的新版 edge-tts，优先级更高
        if os.path.isdir(vdir) and vdir not in sys.path:
            sys.path.insert(0, vdir)
        try:
            import asyncio
            import edge_tts
        except ImportError:
            die("engine=edge 需要 edge-tts：<runtime python> -m pip install edge-tts")
        voice = tts.get("voice") or getattr(args, "edge_voice", "zh-CN-YunxiNeural")
        kw = {f: str(tts[f]) for f in ("rate", "volume", "pitch") if tts.get(f)}
        raw = stem + ".mp3"
        try:
            asyncio.run(edge_tts.Communicate(text, voice, **kw).save(raw))
        except Exception as ex:
            die("edge-tts 合成第 %d 句失败：%r\n"
                "   403 / Invalid response status = 微软那个朗读接口不接受我们这条网络出口\n"
                "   （机房 IP 会被挡，换版本、换 token 都没用；已经连试过 143~152 几个版本串）。\n"
                "   想用它只有两条路：换一个能过微软的代理节点，或者改用\n"
                "   --ai-engine google / --ai-engine baidu / --ai-engine openai。\n"
                "   详细见 README 第六节。" % (entry["index"], ex))
        if not os.path.exists(raw) or os.path.getsize(raw) == 0:
            die("edge-tts 没写出音频（第 %d 句）：检查网络，或换一个 --edge-voice" % entry["index"])
        return raw

    if engine == "sapi":
        try:
            import win32com.client
        except ImportError:
            die("engine=sapi 需要 pywin32：<runtime python> -m pip install pywin32")
        raw = os.path.abspath(stem + ".wav")
        if os.path.exists(raw):
            os.remove(raw)
        want = str(tts.get("voice") or getattr(args, "sapi_voice", "") or "").strip().lower()
        stream = win32com.client.Dispatch("SAPI.SpFileStream")
        stream.Open(raw, 3)                                   # 3 = SSFMCreateForWrite
        sp = win32com.client.Dispatch("SAPI.SpVoice")
        if want:
            for v in sp.GetVoices():
                if want in v.GetDescription().lower():
                    sp.Voice = v
                    break
            else:
                warn("SAPI 里没有 %r，用系统默认那个（可选 Kangkang / Yaoyao / Huihui）" % want)
        sp.AudioOutputStream = stream
        try:
            sp.Rate = max(-10, min(10, int(tts.get("rate", 0))))
        except (TypeError, ValueError):
            pass
        try:
            sp.Volume = max(0, min(100, int(tts.get("volume", 100))))
        except (TypeError, ValueError):
            pass
        sp.Speak(text)
        stream.Close()
        return raw

    die("不认识的 engine: %r" % engine)


def synth_ai_line(engine, tts, entry, lines_dir, args, ff):
    """在线引擎合成的一句，过一道质检再交给后面的流程：

      1) 掐掉开头/结尾的底噪、气口（在线引擎爱在这句前面吐两三秒「滋滋」声，
         听着像多念了一个字，也把这一句撑得比实际长）；
      2) 拿「该多长」比一比 —— 短太多 = 吞字，长太多 = 念重了，两种都重合成。

    以前这里是拿到音频直接落盘，所以才会出现「整句被跳过」——
    第 10 句 28 个字只出了 0.70 秒、第 22 句 38 个字只出了 1.18 秒，
    都是服务端偶尔只回一小段，脚本却照收。本机 GPT-SoVITS 那条路本来就有
    这套自查（见 cmd_synth 的 gsv 分支），现在两边一致了。"""
    import numpy as np
    import soundfile as sf
    text = (entry.get("text") or "").strip()
    speed = float(tts.get("speed") or 1.0)
    want = expected_seconds(text, speed)
    lo, hi = want * SHORT_RATIO, max(want * LONG_RATIO, want + 3.0)
    tries = max(0, int(getattr(args, "synth_retry", 2)))
    dst = os.path.join(lines_dir, ".raw_ai_%04d_trim.wav" % entry["index"])

    best = None
    for attempt in range(tries + 1):
        raw = _synth_ai_raw(engine, tts, entry, lines_dir, args, ff)
        to_pcm_wav(ff, raw, dst)
        if raw and os.path.abspath(raw) != os.path.abspath(dst):
            try:
                os.remove(raw)
            except OSError:
                pass
        wav, sr = sf.read(dst, dtype="float32", always_2d=False)
        wav = trim_head_noise(np.asarray(wav).reshape(-1), sr)
        dur = wav.size / float(sr)
        score = abs(np.log(max(dur, 0.05) / want))       # 离「该有的长度」最近的那一遍留下
        if best is None or score < best[0]:
            best = (score, dur, wav, sr)
        if lo <= dur <= hi:
            break
        if attempt < tries:
            log("  ! 第 %d 句「%s」这一遍 %.2f 秒（该有 %.2f 秒左右）%s，重新合成…（%d/%d）"
                % (entry["index"], text[:16], dur, want,
                   "太短，吞字了" if dur < lo else "太长，可能念重了", attempt + 1, tries))

    score, dur, wav, sr = best
    sf.write(dst, wav, sr, subtype="PCM_16")
    if not (lo <= dur <= hi):
        warn("第 %d 句「%s」合了 %d 遍都不对（最好的一遍 %.2f 秒，该有 %.2f 秒左右）。\n"
             "   这是在线引擎这一趟没念好，不是脚本的问题：重跑一次多半就好了，\n"
             "   也可以把这句话改短点，或者换个 voice 再听。"
             % (entry["index"], text[:16], tries + 1, dur, want))
    return dst


def ai_defaults():
    """从 input\\script.json 里捞 API key / 接口地址 / 模型名，试听时就不用再敲一遍。"""
    out = {}
    path = os.path.join(IN_DIR, "script.json")
    if not os.path.exists(path):
        return out
    try:
        script = load_json(path)
    except Exception:
        return out
    for spk in (script.get("speakers") or {}).values():
        for fld in ("api_key", "base_url", "model"):
            if isinstance(spk, dict) and spk.get(fld) and fld not in out:
                out[fld] = spk[fld]
    return out


def cmd_voices(args):
    """列出现成音色，省得去翻文档。"""
    log("硅基流动（默认那家）的系统预置音色：CosyVoice2 / MOSS-TTSD 两套模型共用这 8 个。")
    log("")
    log("  %-10s %-5s %-9s %s" % ("音色", "性别", "官方描述", "怎么用"))
    for name, sex, desc in AI_SF_VOICES:
        log("  %-10s %-5s %-9s voice 直接写 \"%s\"" % (name, sex, desc, name))
    log("")
    log("上面就是播客推荐顺序：anna（沉稳）> claire（温柔）> 其余。")
    log("diana（欢快）/ bella（激情）念稿子容易显得轻佻，男声里最强的是 charles（磁性）。")
    log("voice 写短名就行，脚本发现接口不认会自动补成「模型名:音色」。")
    log("")
    log("试听一个：")
    log("  podcast_video.bat sample -e openai -v anna --ai-model FunAudioLLM/CosyVoice2-0.5B")
    log("    ↑ 走的是 script.json 里那把 api_key；结果是 output\\sample_openai-anna_<日期>.mp3")
    log("")
    log("想换另一套模型（MOSS-TTSD 更偏对话感）：把 --ai-model 换成 fnlp/MOSS-TTSD-v0.5")
    return None


def cmd_sample(args):
    """试听：先用一小段话把音色听一遍，合适了再写进 script.json。"""
    engine = tts_engine({"engine": args.engine})
    if engine == "gsv":
        die("sample 是拿来试听现成音色的（google / baidu / openai / edge / sapi）。\n"
            "   本机 GPT-SoVITS 那条路想听效果，直接跑 synth，或者把想听的那句写进 script.txt。")
    out_dir = os.path.abspath(args.out_dir or OUT_DIR)
    tmp_dir = os.path.join(out_dir, ".sample")
    os.makedirs(tmp_dir, exist_ok=True)
    ff = find_ffmpeg(args.ffmpeg)
    tts = {"engine": args.engine}
    if args.voice:
        tts["voice"] = args.voice
    defaults = ai_defaults()
    for src, dst in (("ai_key", "api_key"), ("ai_base", "base_url"), ("ai_model", "model")):
        val = getattr(args, src, None) or defaults.get(dst)
        if val:
            tts[dst] = val
    log("试听 %s / %s%s" % (engine, tts.get("voice") or "默认音色",
                           ("  @ " + tts["model"]) if tts.get("model") else ""))
    text = (args.text or AI_SAMPLE_TEXT).strip()

    if getattr(args, "all_voices", False):
        if engine != "openai":
            die("--all 只对 engine=openai（硅基那 8 个系统预置音色）有意义")
        model = tts.get("model") or AI_MODEL
        short = "CosyVoice2" if "CosyVoice" in model else "MOSS-TTSD"
        dst_dir = os.path.join(out_dir, "voice_test", short)
        os.makedirs(dst_dir, exist_ok=True)
        log("模型 %s，8 个音色各出一遍 -> %s" % (model, dst_dir))
        for i, (vname, sex, desc) in enumerate(AI_SF_VOICES, 1):
            dst = os.path.join(dst_dir, "%02d_%s_%s.mp3" % (i, vname, desc))
            log("  [%d/8] %s  %s %s" % (i, vname, sex, desc))
            raw = synth_ai_line("openai", dict(tts, voice=vname),
                                {"index": i, "key": "B", "text": text}, tmp_dir, args, ff)
            if os.path.exists(dst):
                os.remove(dst)
            shutil.move(raw, dst)
        try:
            os.rmdir(tmp_dir)
        except OSError:
            pass
        log("")
        log("8 个都在这了：%s   （听着合适就把 voice 改成对应名字）" % dst_dir)
        return None

    entry = {"index": 1, "key": "B", "text": text}
    raw = synth_ai_line(engine, tts, entry, tmp_dir, args, ff)
    tag = re.sub(r"[^0-9A-Za-z]+", "-", "%s_%s" % (engine, tts.get("voice") or "default")).strip("-")
    dst = default_out_path(out_dir, "sample_" + tag, os.path.splitext(raw)[1].lstrip("."))
    shutil.move(raw, dst)
    try:
        os.rmdir(tmp_dir)
    except OSError:
        pass
    log("")
    log("试听片段：%s" % dst)
    log("听着合适就把这两行写进 input\\script.json 的 speakers.B（照抄，包括逗号）：")
    log('  "engine": "%s",' % engine)
    log('  "voice":  "%s"' % (tts.get("voice") or ""))
    return None


def cmd_synth(args):
    src = getattr(args, "script", None) or getattr(args, "text", None)
    if not src:
        die("没给脚本。用 --script input\\script.json，或者 --text input\\script.txt")
    script_path = os.path.abspath(src)
    if not os.path.exists(script_path):
        die("找不到脚本文件: %s" % script_path)

    script, text_path, cfg_path = {}, None, None
    if script_path.lower().endswith((".txt", ".md")):
        # 台词单独写在 txt 里；配置（说话人/音色/参考音频）从同目录的 script.json 读
        text_path = script_path
        cfg = os.path.join(os.path.dirname(script_path), "script.json")
        if os.path.exists(cfg):
            script = load_json(cfg)
            cfg_path = cfg
    else:
        script = load_json(script_path)
        t = script.get("text") or script.get("text_file")
        cand = resolve_path(t, os.path.dirname(script_path)) if t \
            else os.path.join(os.path.dirname(script_path), "script.txt")
        if cand and os.path.exists(cand):
            text_path = cand
    base = os.path.dirname(text_path or script_path)

    out_dir = os.path.abspath(args.out_dir or OUT_DIR)
    lines_dir = os.path.join(out_dir, "lines")
    os.makedirs(lines_dir, exist_ok=True)
    ff = find_ffmpeg(args.ffmpeg)

    root = args.root or os.environ.get("GSV_ROOT") or default_root()
    root = os.path.abspath(root) if root else None
    args.ref = resolve_path(args.ref, base, root) if args.ref else None
    spks = normalize_speakers(script, args, base, root)
    gap0 = float(script.get("gap", args.gap))
    if text_path:
        entries = parse_script_txt(text_path, spks, gap0)
        log("[台词] %s -> %d 句；声音配置 %s"
            % (text_path, len(entries), cfg_path or script_path))
    else:
        entries = entries_from_lines(script.get("lines") or [], spks, gap0, base, root)

    sweep_lines_dir(lines_dir, entries)
    todo = [e for e in entries if not e["audio"]]
    if todo:
        import numpy as np
        import soundfile as sf

        def eng_of(k):
            return tts_engine(spks[k]["tts"])

        gsv_todo = [e for e in todo if eng_of(e["key"]) == "gsv"]
        log("=" * 68)
        log("要合成 %d 句（另 %d 句用现成文件）" % (len(todo), len(entries) - len(todo)))
        for k in dict.fromkeys(e["key"] for e in todo):
            if eng_of(k) != "gsv":
                cfg_ai = spks[k]["tts"]
                log("  %s : 用现成 AI 配音（%s %s%s）"
                    % (k, eng_of(k), cfg_ai.get("voice") or "",
                       ("  @ " + str(cfg_ai["model"])) if cfg_ai.get("model") else ""))
        log("输出 : %s" % out_dir)
        log("=" * 68)

        get_tts_wav = None
        if gsv_todo:
            if not root or not os.path.isdir(root):
                die("要合成语音就得给 --root <GPT-SoVITS 仓库根目录>（有 webui.py 的那层）")
            for k in dict.fromkeys(e["key"] for e in gsv_todo):
                if not spks[k]["tts"].get("ref"):
                    die("说话人 %s 要合成，但没给参考音频：在 script.json 的 speakers.%s.ref 里写一段\n"
                        "   3~10 秒的干净人声，或者用 --ref 给个全局默认。" % (k, k))
            for k in dict.fromkeys(e["key"] for e in gsv_todo):
                ref = spks[k]["tts"]["ref"]
                if not os.path.exists(ref):
                    die("说话人 %s 的参考音频不存在: %s" % (k, ref))
                rd = probe_duration(ff, ref)
                if rd and not (3.0 <= rd <= 10.0):
                    die("说话人 %s 的参考音频长 %.2f 秒，GPT-SoVITS 只收 3~10 秒。\n"
                        "   先裁一段（比如 9.9 秒）：\n"
                        "     \"%s\" -y -i \"%s\" -t 9.9 -ac 1 -ar 24000 \"裁好的.wav\"\n"
                        "   然后把 speakers.%s.ref 指到裁好的文件，ref_text 改成裁剪后音频里真正说的话。"
                        % (k, rd, ff, ref, k))
            log("仓库 : %s" % root)
            iw, cg, cs, get_tts_wav = load_tts_engine(root, args.version, args.cpu, args.half)

            def lang_key(alias):
                code = LANG_ALIAS.get(str(alias).strip().lower(), str(alias).strip())
                for k, v in iw.dict_language.items():
                    if v == code:
                        return k
                die("语种 %r 这个版本不支持，支持的有：%s" % (alias, list(iw.dict_language.values())))

            loaded = {"w": None, "cut": None, "v": None}

        for e in entries:
            if e["audio"]:
                continue
            tts = spks[e["key"]]["tts"]
            if eng_of(e["key"]) != "gsv":
                t0 = time.time()
                e["audio"] = synth_ai_line(eng_of(e["key"]), tts, e, lines_dir, args, ff)
                log("  [%d/%d] %s  %s  %.1fs  %s"
                    % (e["index"], len(entries), e["key"], eng_of(e["key"]),
                       time.time() - t0, e["text"][:22]))
                continue
            gptp, sovitsp = tts.get("gpt") or args.gpt, tts.get("sovits") or args.sovits
            gpt = (resolve_path(gptp, base, root) if gptp
                   else newest(os.path.join(root, "GPT_weights_" + args.version), ".ckpt"))
            sovits = (resolve_path(sovitsp, base, root) if sovitsp
                      else newest(os.path.join(root, "SoVITS_weights_" + args.version), ".pth"))
            if not gpt or not os.path.exists(gpt):
                die("说话人 %s 找不到 GPT 权重，用 speakers.%s.gpt 指一个" % (e["key"], e["key"]))
            if not sovits or not os.path.exists(sovits):
                die("说话人 %s 找不到 SoVITS 权重，用 speakers.%s.sovits 指一个" % (e["key"], e["key"]))
            pl = lang_key(tts.get("ref_lang") or args.ref_lang)
            tl_ = lang_key(tts.get("lang") or args.lang)
            if loaded["w"] != (gpt, sovits):
                t0 = time.time()
                cg(gpt)
                for _ in cs(sovits, pl, tl_):
                    pass
                loaded["w"] = (gpt, sovits)
                log("[权重] %s / %s  (%.1fs)" % (os.path.basename(gpt), os.path.basename(sovits),
                                               time.time() - t0))
            ck = tts.get("cut") or args.cut
            if loaded["cut"] != ck:
                loaded["cut"], loaded["v"] = ck, iw.i18n(ck)
            seed = tts.get("seed", args.seed)
            if seed is not None and int(seed) >= 0:
                iw.set_seed(int(seed))
                tries = 0            # 钉死了种子，重试也是同一份结果，省掉
            else:
                tries = max(0, int(getattr(args, "synth_retry", 2)))
            ref = tts["ref"]
            if not os.path.exists(ref):
                die("说话人 %s 的参考音频不存在: %s" % (e["key"], ref))
            t0 = time.time()
            speed = float(tts.get("speed", args.speed))
            if getattr(args, "clause_split", False):
                # 自己按逗号切小口：每小口单独合成 + 单独检查时长，
                # 这样「一小口整段没了」物理上不可能发生（见 README 第十一节）。
                pieces = merge_short(split_clauses(e["text"]), 6) or [e["text"]]
            else:
                # 整句一次过：语速最自然、最省时间，但吞字只能在事后发现
                pieces = [e["text"]]
            sr, chunks, retried = None, [], 0
            for pi, piece in enumerate(pieces, 1):
                label = "%d-%d" % (e["index"], pi) if len(pieces) > 1 else str(e["index"])
                want = expected_seconds(piece, speed)
                best = None
                for attempt in range(tries + 1):
                    try:
                        res = list(get_tts_wav(
                            ref_wav_path=ref, prompt_text=tts.get("ref_text") or "",
                            prompt_language=pl, text=piece, text_language=tl_,
                            top_k=int(tts.get("top_k", args.top_k)),
                            top_p=float(tts.get("top_p", args.top_p)),
                            temperature=float(tts.get("temperature", args.temperature)),
                            speed=speed, how_to_cut=loaded["v"]))
                    except Exception as ex:
                        die("第 %s 句合成失败：%r" % (label, ex))
                    sr, wav = res[-1]
                    dur = len(wav) / float(sr)
                    if best is None or dur > best[0]:
                        best = (dur, wav)
                    if dur >= want * SHORT_RATIO or attempt >= tries:
                        break
                    retried += 1
                    log("  ! 第 %s 句「%s」只出了 %.2f 秒（该有 %.2f 秒左右），换个随机种子重来…"
                        % (label, piece, dur, want))
                chunks.append(trim_silence(best[1], sr))
            wav = np.concatenate(chunks) if len(chunks) > 1 else chunks[0]
            tmp = os.path.join(lines_dir, ".raw_%04d.wav" % e["index"])
            sf.write(tmp, wav, sr)
            e["audio"] = tmp
            log("  [%d/%d] %s  %.1fs  %.2fs  %s%s  %s"
                % (e["index"], len(entries), e["key"], time.time() - t0,
                   len(wav) / float(sr),
                   ("%d 小口" % len(pieces)) if len(pieces) > 1 else "整句",
                   ("，重试 %d 次" % retried) if retried else "", e["text"][:22]))

    gains = {}
    if getattr(args, "match_level", True) and entries:
        gains = plan_level_gains(entries, ff, float(getattr(args, "match_target", -20.0)))

    log("")
    log("统一成 %d Hz 单声道并拼接…" % SR)
    for e in entries:
        dst = os.path.join(lines_dir, "%04d_%s.wav" % (e["index"], e["key"]))
        if os.path.abspath(e["audio"]) != os.path.abspath(dst):
            if not os.path.exists(e["audio"]):
                die("第 %d 句的音频不存在: %s" % (e["index"], e["audio"]))
            g = float(gains.get(e["key"], 0.0))
            to_pcm_wav(ff, e["audio"], dst,
                       af=("volume=%.2fdB" % g) if abs(g) >= 0.05 else None)
            if os.path.basename(e["audio"]).startswith(".raw_"):
                try:
                    os.remove(e["audio"])
                except OSError:
                    pass
            e["audio"] = dst
    master = os.path.join(out_dir, "master.wav")
    for e in entries:
        e["wav"] = e["audio"]
    dur = merge_lines(entries, master)
    tl = {"version": 1, "title": script.get("title") or args.title or "", "audio": "master.wav",
          "duration": round(dur, 3), "sample_rate": SR,
          "speakers": {k: {"name": v["name"], "color": v["color"]} for k, v in spks.items()},
          "lines": []}
    for e in entries:
        s = spks[e["key"]]
        tl["lines"].append({
            "index": e["index"], "speaker": e["key"], "name": s["name"], "color": s["color"],
            "text": e["text"], "start": round(e["start"], 3), "duration": round(e["duration"], 3),
            "end": round(e["end"], 3),
            "gain_db": float(gains.get(e["key"], 0.0)),
            "file": os.path.relpath(e["audio"], out_dir).replace("\\", "/")})
    tl_path = os.path.join(out_dir, "timeline.json")
    write_json(tl_path, tl)
    log("")
    log("完成：%d 句 / %.1f 秒（%.1f 分钟）" % (len(entries), dur, dur / 60.0))
    log("  master   : %s" % master)
    log("  timeline : %s" % tl_path)
    return tl_path


# ---------------------------------------------------------------- render
def collect_broll(folder, ff, dur, args):
    """挑素材、统一规格、排成一个够长的播放列表。返回列表文件路径。"""
    if not os.path.isdir(folder):
        die("--broll 指的不是目录: %s" % folder)
    clips = []
    for r, _d, files in os.walk(folder):
        for f in files:
            if f.lower().endswith(VIDEO_EXTS):
                clips.append(os.path.join(r, f))
    if not clips:
        die("--broll 目录里没有视频文件: %s" % folder)
    seed = int(getattr(args, "seed", 7) or 0)
    if args.broll_order == "random":
        random.Random(seed).shuffle(clips)
    if args.broll_limit and len(clips) > args.broll_limit:
        clips = clips[:args.broll_limit]
    chosen, total = [], 0.0
    for c in clips:
        d = probe_duration(ff, c)
        if not d or d < 0.5:
            warn("跳过读不出时长的素材: %s" % c)
            continue
        chosen.append((c, d))
        total += min(d, args.broll_max)
        if total >= dur * 1.1:
            break
    if not chosen:
        die("没有可用素材")
    log("[b-roll] 抽中 %d 段（够 %.0f 秒，需要 %.0f 秒）" % (len(chosen), total, dur))
    rng = random.Random(seed + 1)
    cache = os.path.join(args._work, ".broll_cache")
    os.makedirs(cache, exist_ok=True)
    use_x264 = probe_ffmpeg(ff)["x264"]
    names, total_n = [], 0.0
    for c, d in chosen:
        seg = min(rng.uniform(args.broll_min, args.broll_max), max(1.0, d))
        key = hashlib.sha1(("|".join([os.path.abspath(c), str(os.path.getmtime(c)),
                                      str(os.path.getsize(c)), str(args.W), str(args.H),
                                      str(args.fps), "%.2f" % seg])).encode("utf-8")).hexdigest()[:16]
        out = os.path.join(cache, key + (".mp4" if use_x264 else ".webm"))
        if not os.path.exists(out):
            vf = ("scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1,fps=%d"
                  % (args.W, args.H, args.W, args.H, args.fps))
            enc = (["-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p"]
                   if use_x264 else ["-c:v", "libvpx-vp9", "-crf", "32", "-b:v", "0", "-row-mt", "1"])
            run([ff, "-y", "-hide_banner", "-loglevel", "error", "-i", c, "-t", "%.2f" % seg,
                 "-an", "-vf", vf] + enc + [out], quiet=True)
        names.append(os.path.relpath(out, args._work).replace("\\", "/"))
        total_n += seg
    reps = max(1, int(dur / max(total_n, 0.1)) + 1)
    lst = os.path.join(args._work, ".broll.txt")
    with open(lst, "w", encoding="utf-8") as f:
        for _ in range(reps):
            for n in names:
                f.write("file '%s'\n" % n)
    log("[b-roll] 规格统一成 %dx%d，列表重复 %d 遍（素材间会跳切）" % (args.W, args.H, reps))
    return lst


def cmd_render(args):
    default_render_paths(args)
    tl_path = os.path.abspath(getattr(args, "timeline", "") or "")
    if not os.path.exists(tl_path):
        die("render 需要 --timeline <timeline.json>（synth 会生成）")
    work = os.path.dirname(tl_path)
    args._work = work
    tl = load_json(tl_path)
    ff = find_ffmpeg(args.ffmpeg)
    caps = probe_ffmpeg(ff)
    W, H = parse_size(args.size or "1080x1920")
    args.W, args.H, args.fps = W, H, int(args.fps or 25)
    args.accent = norm_hex(args.accent, (getattr(args, "_theme", None) or theme_of({}))["accent"])

    master = tl.get("audio") or "master.wav"
    if not os.path.isabs(master):
        master = os.path.join(work, master)
    if not os.path.exists(master):
        die("时间轴指的音频不存在: %s" % master)
    dur = probe_duration(ff, master) or float(tl.get("duration") or 0)
    if not dur or dur <= 0:
        die("读不出音频时长: %s" % master)
    tl["duration"] = dur

    mode = args.mode or "auto"
    if mode == "auto":
        mode = "broll" if args.broll else "cover"
    if not caps["x264"]:
        warn("ffmpeg 没有 libx264，导出 WebM/VP9。要发抖音小红书建议换完整版。")
    no_subs = bool(args.no_subs)
    if not no_subs and not caps["ass"]:
        warn("这个 ffmpeg 没有 libass，字幕烧不进去，这次先不烧。")
        no_subs = True
    vis = args.visual or "wave"
    if vis != "none" and not caps["showwaves"]:
        warn("这个 ffmpeg 没有 showwaves/showspectrum，跳过音频可视化。")
        vis = "none"
    normalize = (not args.no_normalize) and caps.get("loudnorm", False)
    if not args.no_normalize and not caps.get("loudnorm", False):
        warn("这个 ffmpeg 没有 loudnorm，跳过响度归一。")

    pb = max(6, int(H * 0.005)) if args.progress is not False else 0
    n_spk = len(tl.get("speakers") or {}) or 1
    th = getattr(args, "_theme", None) or theme_of({})
    sc = getattr(args, "sub_color", None)
    if sc is None:
        sub_fg = th["sub"]            # 跟主题：一般一水儿的象牙白，最干净
    elif str(sc).strip().lower() in ("speaker", "spk", "color", "self"):
        sub_fg = None                 # 按说话人上色（老风格）
    else:
        sub_fg = norm_hex(str(sc), th["sub"] or "FFFFFF")
    opt = {"W": W, "H": H, "pb": pb, "accent": args.accent, "font": args.font,
           "sub_margin": args.sub_margin, "wrap": args.wrap,
           "sub_size": args.sub_size, "title_size": args.title_size,
           "who_size": args.who_size, "who_y": args.who_y, "sub_fg": sub_fg,
           "title": args.title or tl.get("title") or None,
           "subtitle": args.subtitle or None,
           "who": True,
           "speaker_tag": bool(args.speaker_tag) and n_spk > 1 and not no_subs,
           "show_name": bool(args.name)}
    ass_rel = None
    if not no_subs:
        write_ass(os.path.join(work, "subs.ass"), tl, opt)
        ass_rel = "subs.ass"

    inputs, graph = [], []
    cover = None
    if mode == "cover":
        cover = args.cover
        if not cover:
            cover = os.path.join(work, ".auto_cover.png")
            try:
                make_cover(cover, W, H, args.accent, bg=args.bg, circle=args.circle,
                           no_circle=bool(args.no_circle))
                log("[封面] 自动生成 %s（整张换 --cover 或 input\\cover.png；"
                    "只换底图 / 中间那张圆图看 input\\bg.png、input\\circle.png）" % cover)
            except Exception as ex:
                warn("自动画封面失败（%s），改用纯色底" % ex)
                cover = None
        if cover:
            inputs += ["-loop", "1", "-framerate", str(args.fps), "-i", os.path.abspath(cover)]
        else:
            inputs += ["-f", "lavfi", "-i", "color=c=0x0e1016:s=%dx%d:r=%d" % (W, H, args.fps)]
    else:
        inputs += ["-f", "concat", "-safe", "0", "-i", collect_broll(args.broll, ff, dur, args)]
    inputs = ["-i", master] + inputs

    graph.append("[1:v]scale=%d:%d:force_original_aspect_ratio=increase,crop=%d:%d,setsar=1,"
                 "fps=%d[bg0]" % (W, H, W, H, args.fps))
    scrim = 0.45 if args.scrim is None else float(args.scrim)
    if scrim > 0:
        # 渐变压暗：切成 24 条越来越黑的横条，比一整块灰 box 自然得多（看不出接缝）
        y0, steps = int(H * 0.44), 24
        boxes = []
        for i in range(steps):
            ya = y0 + (H - y0) * i // steps
            yb = y0 + (H - y0) * (i + 1) // steps
            boxes.append("drawbox=x=0:y=%d:w=%d:h=%d:color=black@%.3f:t=fill"
                         % (ya, W, yb - ya, scrim * ((i + 1) / float(steps)) ** 1.6))
        graph.append("[bg0]" + ",".join(boxes) + "[bg]")
    else:
        graph.append("[bg0]null[bg]")

    cur = "bg"
    if vis != "none":
        band = int(H * (0.56 if mode == "broll" else 0.60))
        if vis == "both":
            order = [("spec", int(H * 0.12), band), ("wave", int(H * 0.11), band + int(H * 0.12))]
        elif vis == "spec":
            order = [("spec", int(H * 0.18), band)]
        else:
            order = [("wave", int(H * 0.13), band)]
        for j, (kind, hh, yy) in enumerate(order, 1):
            nxt = "v%d" % j
            if kind == "wave":
                # 白色波形 + 按主题色染色：showwaves 自己上色会随音量/密度串色
                # （重口音频会渲染成紫色），先画白的再乘色相就锁死了。
                # scale=sqrt 让小音量也看得见；aa=1.3 把线压实一点，
                # 不然细波形在 yuv420p 里被抽掉色度，看着发灰发闷。
                r, g, b = (int(args.accent[i:i + 2], 16) for i in (0, 2, 4))
                graph.append("[0:a]showwaves=s=%dx%d:mode=cline:rate=%d:colors=0xFFFFFF:scale=sqrt,"
                             "format=rgba,lutrgb=r='val*%d/255':g='val*%d/255':b='val*%d/255',"
                             "colorchannelmixer=aa=1.3[wave]"
                             % (W, hh, args.fps, r, g, b))
            else:
                graph.append("[0:a]showspectrum=s=%dx%d:mode=combined:color=intensity:scale=log:"
                             "slide=scroll:legend=0,format=yuva420p,colorchannelmixer=aa=0.50[spec]"
                             % (W, hh))
            graph.append("[%s][%s]overlay=x=0:y=%d:format=auto[%s]" % (cur, kind, yy, nxt))
            cur = nxt
    if ass_rel:
        graph.append("[%s]ass=%s[vsub]" % (cur, ass_rel))
        cur = "vsub"
    if pb:
        graph.append("[%s]drawbox=x=0:y=0:w=%d:h=%d:color=white@0.12:t=fill,"
                     "drawbox=x=0:y=0:w='%d*t/%.3f':h=%d:color=0x%s@0.92:t=fill[vpb]"
                     % (cur, W, pb, W, dur, pb, args.accent))
        cur = "vpb"
    amap = "0:a"
    if normalize:
        graph.append("[0:a]loudnorm=I=-16:TP=-1.5:LRA=11[aout]")
        amap = "[aout]"
    graph.append("[%s]format=yuv420p[out]" % cur)

    out = os.path.abspath(args.out or default_out_path(
        work, "podcast", "mp4" if caps["x264"] else "webm"))
    if caps["x264"]:
        ven = ["-c:v", "libx264", "-preset", args.preset, "-crf", str(args.crf),
               "-profile:v", "high", "-pix_fmt", "yuv420p", "-movflags", "+faststart"]
    else:
        ven = ["-c:v", "libvpx-vp9", "-crf", str(max(28, args.crf + 8)), "-b:v", "0",
               "-row-mt", "1", "-deadline", "good", "-cpu-used", "2"]
    cmd = ([ff, "-y", "-hide_banner", "-loglevel", "warning", "-stats"] + inputs
           + ["-filter_complex", ";".join(graph), "-map", "[out]", "-map", amap] + ven
           + ["-c:a", "aac", "-b:a", "192k", "-t", "%.3f" % dur, out])
    log("")
    log("[render] %s  %dx%d @%dfps  %.1f 秒（%.1f 分钟）" % (mode, W, H, args.fps, dur, dur / 60.0))
    if cover:
        src = cover
    elif args.broll:
        src = args.broll
    elif args.bg:
        src = "自动封面（底图 %s）" % os.path.basename(args.bg)
    else:
        src = "自动封面"
    log("[render] 配色=%s 字体=%s 可视化=%s 背景=%s 字幕=%s 响度归一=%s"
        % (th["name"], args.font or pick_default_font(), vis, src,
           "on" if ass_rel else "off", "on" if normalize else "off"))
    if args.debug:
        log("    $ " + " ".join(cmd))
    t0 = time.time()
    run(cmd, cwd=work, quiet=True, stream=True)
    log("")
    log("完成 %.0fs -> %s" % (time.time() - t0, out))
    return out


# ---------------------------------------------------------------- demo
DEMO_LINES = [
    ("A", "哈喽，欢迎收听第 1 期节目。今天想聊聊，为什么做一支播客视频，比录一段音频要费劲得多。"),
    ("B", "嗯，我猜是因为人耳能忍的东西，人眼忍不了。同一段声音配上静止画面，你就开始盯着字幕挑错别字了。"),
    ("A", "所以我们今天把这条流水线搭起来：一句一句地合成，再一句一句地上字幕。"),
    ("B", "那进度条呢？我觉得进度条是短视频里最被低估的东西。"),
    ("A", "所以它排在最上面，一直在动。你看，它现在就在动。"),
]


def cmd_demo(args):
    out_dir = os.path.abspath(args.out_dir or OUT_DIR)
    lines_dir = os.path.join(out_dir, "lines")
    os.makedirs(lines_dir, exist_ok=True)
    ff = find_ffmpeg(args.ffmpeg)
    apply_video_cfg(args)              # 跟 input\script.json 走：主题色 / 标题 / 说话人名
    th = getattr(args, "_theme", None) or theme_of({})
    cfg = {}
    sp = getattr(args, "script", None) or os.path.join(IN_DIR, "script.json")
    if os.path.exists(sp):
        try:
            cfg = load_json(sp) or {}
        except Exception:
            cfg = {}
    src_spk = cfg.get("speakers") or {}
    rng = random.Random(7)
    entries = []
    for i, (spk, text) in enumerate(DEMO_LINES, 1):
        raw = os.path.join(lines_dir, ".raw_%04d.wav" % i)
        make_test_audio(ff, rng.uniform(2.6, 4.6), raw)
        dst = os.path.join(lines_dir, "%04d_%s.wav" % (i, spk))
        to_pcm_wav(ff, raw, dst)
        os.remove(raw)
        entries.append({"wav": dst, "gap": 0.45, "start": 0.0, "duration": 0.0, "end": 0.0,
                        "key": spk, "text": text})
    master = os.path.join(out_dir, "master.wav")
    dur = merge_lines(entries, master)
    names, colors = {}, {}
    for i, k in enumerate(("A", "B")):
        v = src_spk.get(k) or {}
        names[k] = v.get("name") or ("小希" if k == "A" else "唠嗑")
        colors[k] = norm_hex(v.get("color"), th["colors"][i % len(th["colors"])])
    tl = {"version": 1, "title": cfg.get("title") or "AI 生活进行时", "audio": "master.wav",
          "duration": round(dur, 3), "sample_rate": SR,
          "speakers": {k: {"name": names[k], "color": colors[k]} for k in names},
          "lines": []}
    for e in entries:
        tl["lines"].append({"index": len(tl["lines"]) + 1, "speaker": e["key"],
                            "name": names[e["key"]], "color": colors[e["key"]],
                            "text": e["text"], "start": round(e["start"], 3),
                            "duration": round(e["duration"], 3), "end": round(e["end"], 3),
                            "file": "lines/" + os.path.basename(e["wav"])})
    p = os.path.join(out_dir, "timeline.json")
    write_json(p, tl)
    log("demo 造好了：%s（%.1f 秒）" % (out_dir, dur))
    log("注意：demo 里的声音是**测试音**（正弦波），不是人声，只为看版式。")
    log("     要听真声：synth（用 GPT-SoVITS 合成）或 from-lines（拿现成的逐句 wav）。")
    args.timeline = p
    if not args.mode or args.mode == "auto":
        args.mode = "cover"
    if not args.title:
        args.title = tl["title"]
    if not args.out:
        args.out = default_out_path(out_dir, "demo", "mp4")
    return cmd_render(args)


def cmd_from_lines(args):
    """拿一个目录里的现成逐句音频直接出片（比如 GPT-SoVITS 的 tts_out）

    GPT-SoVITS 一句一个 wav，顺序就是文件名顺序；文本可以另外给一个一行一句的 txt，
    音频和文本按顺序一一对应。已有音频就不用再合成一遍了。
    """
    d = os.path.abspath(args.dir)
    if not os.path.isdir(d):
        die("--dir 指的不是目录: %s" % d)
    files = sorted(os.path.join(d, f) for f in os.listdir(d)
                   if f.lower().endswith(AUDIO_EXTS) and not f.lower().startswith("merged_")
                   and f.lower() != "master.wav")
    if not files:
        die("--dir 里没找到音频文件: %s" % d)
    texts = []
    if args.text_file:
        with open(os.path.abspath(args.text_file), encoding="utf-8-sig") as f:
            texts = [ln.strip() for ln in f if ln.strip()]
        if len(texts) != len(files):
            warn("文本 %d 行、音频 %d 个，对不上：按顺序一一对应，多出来的会被忽略"
                 % (len(texts), len(files)))
    else:
        warn("没给 --text-file，字幕就拿文件名当文本（想干净点就加 --no-subs）")
        texts = [re.sub(r"^\d+[_\-\s]*", "", os.path.splitext(os.path.basename(p))[0])
                 for p in files]
    ff = find_ffmpeg(args.ffmpeg)
    work = os.path.abspath(args.out_dir or OUT_DIR)
    lines_dir = os.path.join(work, "lines")
    os.makedirs(lines_dir, exist_ok=True)
    log("[from-lines] %d 句，来自 %s" % (len(files), d))
    items = []
    for i, p in enumerate(files, 1):
        items.append({"wav": to_pcm_wav(ff, p, os.path.join(lines_dir, "%04d.wav" % i)),
                      "gap": args.gap, "start": 0.0, "duration": 0.0, "end": 0.0})
    master = os.path.join(work, "master.wav")
    total = merge_lines(items, master)
    spk = {"name": args.speaker or "我", "color": args.accent}
    tl = {"version": 1, "title": args.title or "", "audio": "master.wav",
          "duration": round(total, 3), "sample_rate": SR, "speakers": {"A": spk}, "lines": []}
    for i, it in enumerate(items, 1):
        tl["lines"].append({
            "index": i, "speaker": "A", "name": spk["name"], "color": spk["color"],
            "text": texts[i - 1] if i <= len(texts) else "",
            "start": round(it["start"], 3), "duration": round(it["duration"], 3),
            "end": round(it["end"], 3), "file": "lines/%04d.wav" % i})
    tp = os.path.join(work, "timeline.json")
    write_json(tp, tl)
    log("[from-lines] %.1f 秒（%.1f 分钟）-> %s" % (total, total / 60.0, tp))
    args.timeline = tp
    return cmd_render(args)


# ---------------------------------------------------------------- auto（双击默认）
def cmd_transcribe(args):
    """换个参考音频就得重新写 ref_text —— 这个命令用本机缓存里的 FunASR 转写，
    不联网、不用装东西（模型在 GPT-SoVITS 的 tools\\asr\\models\\ 里）。"""
    d = os.path.abspath(args.dir)
    if not os.path.isdir(d):
        die("--dir 指的不是目录: %s" % d)
    files = sorted(os.path.join(d, f) for f in os.listdir(d)
                   if f.lower().endswith(AUDIO_EXTS))
    if not files:
        die("--dir 里没有音频文件: %s" % d)
    root = args.root or os.environ.get("GSV_ROOT") or default_root()
    if not root or not os.path.isdir(root):
        die("转写要用 GPT-SoVITS 里的 FunASR 模型，给个 --root <GPT-SoVITS 仓库根目录>")
    home = os.getcwd()
    try:
        os.chdir(root)
        sys.path.insert(0, root)
        try:
            from funasr import AutoModel
        except ImportError as ex:
            die("导不进 funasr：%r\n   用 GPT-SoVITS 自带的 runtime\\python.exe 跑这个命令。" % (ex,))
        log("[转写] 加载 FunASR（第一次要十几秒）…")
        model = AutoModel(
            model="tools/asr/models/speech_paraformer-large_asr_nat-zh-cn-16k-common-vocab8404-pytorch",
            model_revision="v2.0.4",
            vad_model="tools/asr/models/speech_fsmn_vad_zh-cn-16k-common-pytorch",
            vad_model_revision="v2.0.4",
            punc_model="tools/asr/models/punc_ct-transformer_zh-cn-common-vocab272727-pytorch",
            punc_model_revision="v2.0.4",
            disable_update=True)
        for p in files:
            try:
                text = model.generate(input=p)[0]["text"]
            except Exception as ex:
                text = "!! 转写失败：%r" % (ex,)
            log("")
            log("%s" % os.path.basename(p))
            log("    %s" % text)
    finally:
        os.chdir(home)
    log("")
    log("把上面那行原封不动抄进 script.json 的 ref_text（标点差一个都会让音色飘）。")
    return None


def cmd_auto(args):
    """看 input\\ 里有什么就做什么：
      有 script.txt / script.json -> 合成 + 出片；有 lines\\*.wav -> 拿现成的直接出片；
      都没有 -> 打印「怎么开始」，不报错。"""
    if not getattr(args, "script", None):
        for name in ("script.txt", "script.json"):      # 台词单独写在 script.txt 里，优先用它
            p = os.path.join(IN_DIR, name)
            if os.path.exists(p):
                args.script = p
                break
    script = os.path.abspath(args.script) if args.script else None
    if script and os.path.exists(script):
        log("[auto] 发现脚本：%s" % script)
        args.script = script
        return cmd_render(_with_timeline(args, cmd_synth(args)))
    lines_dir = os.path.abspath(args.dir or os.path.join(IN_DIR, "lines"))
    if os.path.isdir(lines_dir):
        wavs = [f for f in os.listdir(lines_dir)
                if f.lower().endswith(AUDIO_EXTS) and not f.startswith(".")]
        if wavs:
            log("[auto] 发现 %d 句现成音频：%s" % (len(wavs), lines_dir))
            args.dir = lines_dir
            if not args.text_file:
                tf = os.path.join(IN_DIR, "lines.txt")
                args.text_file = tf if os.path.exists(tf) else None
            return cmd_from_lines(args)
    print_getting_started()
    return None


# ---------------------------------------------------------------- CLI
def add_common(p):
    p.add_argument("--ffmpeg", help="ffmpeg 路径（默认自动找带 libx264 的那个）")
    p.add_argument("--size", help="画面尺寸，默认 1080x1920（竖屏），也可以写在 script.json 的 video.size")
    p.add_argument("--fps", help="帧率，默认 25")
    p.add_argument("--debug", action="store_true", help="渲染时把完整命令也打出来")


def add_synth_opts(p, with_title=True):
    p.add_argument("--root", help="GPT-SoVITS 仓库根目录（有 webui.py 的那层）")
    p.add_argument("--version", default="v2Pro", help="权重版本目录后缀，默认 v2Pro")
    p.add_argument("--gpt", help="全局默认 GPT 权重 .ckpt")
    p.add_argument("--sovits", help="全局默认 SoVITS 权重 .pth")
    p.add_argument("--ref", help="全局默认参考音频（3~10 秒干净人声）")
    p.add_argument("--ref-text", dest="ref_text", help="全局默认参考原文（要和音频逐字一致）")
    p.add_argument("--ref-lang", dest="ref_lang", default="zh", help="参考音频语种")
    p.add_argument("--edge-voice", dest="edge_voice", default="zh-CN-YunxiNeural",
                   help="engine=edge 的默认音色，默认 zh-CN-YunxiNeural（云希，男）")
    p.add_argument("--sapi-voice", dest="sapi_voice", default="",
                   help="engine=sapi 的默认声音，如 Kangkang / Yaoyao / Huihui")
    p.add_argument("--ai-engine", dest="ai_engine",
                   help="把 B 那一方整体换成在线音色：google / baidu / openai")
    p.add_argument("--ai-voice", dest="ai_voice",
                   help="在线音色的名字（google: zh-CN；baidu: 0/4；openai: 模型里的音色名）")
    p.add_argument("--ai-speaker", dest="ai_speaker", default="A",
                   help="哪些说话人算『我自己』、不受 --ai-engine 影响，默认 A；多个用逗号隔开")
    p.add_argument("--ai-key", dest="ai_key",
                   help="engine=openai 的 API key（也可以设环境变量 PODCAST_TTS_KEY）")
    p.add_argument("--ai-base", dest="ai_base", help="engine=openai 的接口地址")
    p.add_argument("--ai-model", dest="ai_model", help="engine=openai 的模型名")
    p.add_argument("--lang", default="zh", help="合成文本语种")
    p.add_argument("--cut", default="按标点符号切", help="长文本切句方式")
    p.add_argument("--speed", type=float, default=1.0)
    p.add_argument("--temperature", type=float, default=1.0)
    p.add_argument("--top-k", dest="top_k", type=int, default=15)
    p.add_argument("--top-p", dest="top_p", type=float, default=1.0)
    p.add_argument("--seed", type=int, default=-1, help="固定它便于复现；-1 表示随机")
    p.add_argument("--cpu", action="store_true", help="强制用 CPU")
    p.add_argument("--half", action="store_true", help="强制半精度（有显卡才用）")
    p.add_argument("--gap", type=float, default=0.35, help="句间静音秒数，默认 0.35")
    p.add_argument("--match-level", dest="match_level", action="store_true", default=True,
                   help="按说话人把响度对齐（默认开，解决 A/B 一个响一个轻）")
    p.add_argument("--no-match-level", dest="match_level", action="store_false",
                   help="关掉按说话人的响度对齐，保留原始电平")
    p.add_argument("--match-target", dest="match_target", type=float, default=-20.0,
                   help="对齐到什么响度，单位 LUFS，默认 -20")
    p.add_argument("--synth-retry", dest="synth_retry", type=int, default=2,
                   help="某小口合成出来明显太短（吞字）时最多重试几次，默认 2")
    p.add_argument("--no-synth-check", dest="synth_retry", action="store_const", const=0,
                   help="关掉吞字自查/重试：合成一遍就过，快，但可能丢字")
    p.add_argument("--split-clauses", dest="clause_split", action="store_true", default=False,
                   help="按逗号切小口、逐小口合成：丢一整小口不可能，但语速会慢一些（保险模式）")
    if with_title:
        p.add_argument("--title", help="节目名，写进 timeline.json")


def add_render_opts(p):
    add_common(p)
    p.add_argument("--timeline", help="timeline.json（synth 会生成）")
    p.add_argument("--out", help="输出文件，默认 <时间轴目录>/podcast_<日期时间>.mp4")
    p.add_argument("--mode", choices=["auto", "cover", "broll"],
                   help="auto = 给了 --broll 就 broll，否则 cover")
    p.add_argument("--cover", help="整张封面图（不给就自动生成一张）")
    p.add_argument("--bg", help="自动封面的底图（不给就看 input\\bg.png）；圆圈和标题叠在它上面")
    p.add_argument("--circle", help="圆圈里那张图（不给就看 input\\circle.png；都没有就画同心圆）")
    p.add_argument("--no-circle", dest="no_circle", action="store_true", default=None,
                   help="封面中间不画圆圈")
    p.add_argument("--broll", help="背景视频素材目录（行车记录仪那种，会随机抽）")
    p.add_argument("--broll-min", type=float, default=8.0, help="每段素材最短秒数")
    p.add_argument("--broll-max", type=float, default=15.0, help="每段素材最长秒数")
    p.add_argument("--broll-order", default="random", choices=["random", "seq"])
    p.add_argument("--broll-limit", type=int, default=0, help="最多用几段素材，0=不限")
    p.add_argument("--visual", choices=["wave", "spec", "both", "none"],
                   help="音频可视化：wave 波形（默认）/ spec 频谱 / both / none")
    p.add_argument("--title", help="标题，永远在最上面（默认读 script.json 的 title）")
    p.add_argument("--subtitle", help="标题下面那行小字")
    p.add_argument("--progress", dest="progress", action="store_true", default=None)
    p.add_argument("--no-progress", dest="progress", action="store_false")
    p.add_argument("--no-subs", dest="no_subs", action="store_true", default=None)
    p.add_argument("--name", action="store_true", default=None,
                   help="字幕每句前面再加上说话人名字（默认不加，画面中间已经有大字名字了）")
    p.add_argument("--speaker-tag", dest="speaker_tag", action="store_true", default=None,
                   help="左上角也显示『现在谁在说』（默认不显示，中间已经有名字了）")
    p.add_argument("--no-speaker-tag", dest="speaker_tag", action="store_false",
                   help="和上面相反，一般不用写")
    p.add_argument("--font", help="字体名，默认自动挑（本机有思源宋体就用它）；见 README 附录 B")
    p.add_argument("--sub-size", dest="sub_size", type=int,
                   help="字幕字号（像素）；不给就自动算（竖屏 1080x1920 → 70）")
    p.add_argument("--title-size", dest="title_size", type=int, help="标题字号，默认短边*0.050")
    p.add_argument("--who-size", dest="who_size", type=int, help="中间说话人名字字号，默认短边*0.072")
    p.add_argument("--who-y", dest="who_y", type=float,
                   help="说话人名字在画面高度上的位置，默认 0.455")
    p.add_argument("--wrap", type=int,
                   help="字幕每行最多几个字；不给就按字号自动算（推荐）")
    p.add_argument("--sub-margin", dest="sub_margin", type=float,
                   help="字幕离底部的高度（占画高比例），默认 0.045")
    p.add_argument("--scrim", type=float, help="下半部分压暗程度 0~1，默认 0.45，0 关掉")
    p.add_argument("--no-normalize", dest="no_normalize", action="store_true",
                   help="不做响度归一（默认归一到 -16 LUFS，播客标准）")
    p.add_argument("--accent", help="主题色（圆环 / 波形 / 进度条）；默认跟 script.json 的配色主题")
    p.add_argument("--theme", help="配色主题：ink / celadon / moon / clay / classic（见 README 附录 A）")
    p.add_argument("--sub-color", dest="sub_color",
                   help="字幕正文颜色：speaker = 按说话人上色，或写 #RRGGBB；默认跟主题（象牙白）")
    p.add_argument("--crf", type=int, default=20, help="画质，越小越清晰")
    p.add_argument("--preset", default="faster", help="x264 预设，快一点用 veryfast")


def build_parser():
    ap = argparse.ArgumentParser(description="音频 -> 播客视频（本地离线）")
    ap.add_argument("--version-info", action="version", version="podcast.py " + VERSION)
    sub = ap.add_subparsers(dest="cmd")

    p = sub.add_parser("synth", help="按对话脚本合成语音 -> master.wav + timeline.json")
    p.add_argument("--script", help="script.json（配置 + 台词）或 script.txt（只有台词）")
    p.add_argument("--text", help="纯台词文本，A: / B: 分块（等价于 --script xxx.txt）")
    p.add_argument("--out-dir", help="输出目录，默认 output\\")
    add_synth_opts(p)
    add_common(p)
    p.set_defaults(func=cmd_synth)

    p = sub.add_parser("render", help="timeline.json + 音频 -> mp4")
    add_render_opts(p)
    p.set_defaults(func=cmd_render)

    def do_build(a):
        return cmd_render(_with_timeline(a, cmd_synth(a)))

    p = sub.add_parser("build", help="synth + render 一条龙")
    p.add_argument("--script", help="script.json（配置 + 台词）或 script.txt（只有台词）")
    p.add_argument("--text", help="纯台词文本，A: / B: 分块（等价于 --script xxx.txt）")
    p.add_argument("--out-dir", help="输出目录，默认 output\\")
    add_synth_opts(p, with_title=False)
    add_render_opts(p)
    p.set_defaults(func=do_build)

    p = sub.add_parser("demo", help="造假音频 + 时间轴，先看画面（不需要 GPT-SoVITS）")
    p.add_argument("--out-dir", default=OUT_DIR)
    add_render_opts(p)
    p.set_defaults(func=cmd_demo)

    p = sub.add_parser("from-lines", help="拿现成的逐句音频（如 GPT-SoVITS 的 tts_out）直接出片")
    p.add_argument("--dir", required=True, help="放逐句音频的目录")
    p.add_argument("--text-file", dest="text_file", help="一行一句的文本，和音频按顺序对应")
    p.add_argument("--speaker", default="我", help="说话人显示名，默认『我』")
    p.add_argument("--gap", type=float, default=0.35, help="句间静音秒数，默认 0.35")
    p.add_argument("--out-dir", help="输出目录，默认 output\\")
    add_render_opts(p)
    p.set_defaults(func=cmd_from_lines)

    p = sub.add_parser("transcribe", help="把参考音频转成文字（拿 ref_text 用，离线）")
    p.add_argument("--dir", default=os.path.join(IN_DIR, "ref"), help="音频目录，默认 input\\ref")
    p.add_argument("--root", help="GPT-SoVITS 仓库根目录")
    p.set_defaults(func=cmd_transcribe)

    p = sub.add_parser("voices", help="列出现成的在线音色（哪个适合播客）")
    p.set_defaults(func=cmd_voices)

    p = sub.add_parser("sample", help="试听一个现成的在线音色 -> output\\sample_*.mp3")
    p.add_argument("-e", "--engine", default="google",
                   help="google / baidu / openai / edge / sapi，默认 google")
    p.add_argument("-v", "--voice", help="音色名，见 README 第六节")
    p.add_argument("-t", "--text", help="想让它念的句子，不给就念一句固定的试听词")
    p.add_argument("--all", dest="all_voices", action="store_true",
                   help="把这个模型下 8 个音色一次性都出一遍（挑音色用）")
    p.add_argument("--ai-key", dest="ai_key", help="engine=openai 的 API key")
    p.add_argument("--ai-base", dest="ai_base", help="engine=openai 的接口地址")
    p.add_argument("--ai-model", dest="ai_model", help="engine=openai 的模型名")
    p.add_argument("--out-dir", default=OUT_DIR, help="输出目录，默认 output\\")
    p.add_argument("--ffmpeg")
    p.set_defaults(func=cmd_sample)

    p = sub.add_parser("auto", help="看 input\\ 里有什么就做什么（双击 bat 的默认动作）")
    p.add_argument("--script", help="脚本，默认 input\\script.txt，其次 input\\script.json")
    p.add_argument("--text", help="纯台词文本，A: / B: 分块（等价于 --script xxx.txt）")
    p.add_argument("--dir", help="逐句音频目录，默认 input\\lines")
    p.add_argument("--text-file", dest="text_file", help="逐句文本，默认 input\\lines.txt")
    p.add_argument("--speaker", default="我", help="说话人显示名，默认『我』")
    p.add_argument("--out-dir", help="输出目录，默认 output\\")
    add_synth_opts(p, with_title=False)
    add_render_opts(p)
    p.set_defaults(func=cmd_auto)
    return ap


def _with_timeline(args, tl):
    args.timeline = tl
    return args


def main():
    ap = build_parser()
    args = ap.parse_args()
    if not getattr(args, "cmd", None):
        args = ap.parse_args(["auto"])
    args.func(args)


if __name__ == "__main__":
    main()
