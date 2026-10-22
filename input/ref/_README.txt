把参考音频丢这里：3~10 秒干净人声（wav / mp3 / m4a 都行）。
超过 10 秒 GPT-SoVITS 会拒绝，先裁：
  <ffmpeg> -y -i in.wav -t 9.9 -ac 1 -ar 24000 out.wav

嫌找参考音频麻烦？B 可以直接用免费在线音色，不用这里的文件（README 第六节方案 2）：
  script.json 的 speakers.B 里加两行   "engine": "google",  "voice": "zh-CN"
  先听一句：podcast_video.bat sample -e google -v zh-CN

现在这里有什么（下面的 ref_text 可以直接抄进 script.json）：

  A_ref2_9s.wav          A（你自己）的参考音频  7.00 秒
                         ref_text: 我想通过AI辅助的问答开启一场寻神记，起因是我的大学班主任

  B_female_9s.wav        B 女声  9.90 秒   <- script.json 默认在用
                         ref_text: 喜欢攀岩徒步滑雪的语言爱好者，以及过两天要带着全部家当去景德镇做陶瓷的白日梦想家。

  B_male_9s.wav          B 男声  9.90 秒
                         ref_text: 哦，还有一个就是要跟大家纠正一点，就是我们在看电影的时候，尤其是游戏玩家看电影的时候，在看到那个到西北那边的这个陕北民。

  B_female_mandarin.wav  } 上面两段的原始文件（10.04 秒 / 13.78 秒，
  B_male_mandarin.wav    } 超过 10 秒不能直接用，留着方便你自己重新裁）

换了音频、或者重新裁过，ref_text 就必须重新转写（差一个字音色就会飘），
用本机这份离线转写，不用联网、不用装东西：
  podcast_video.bat transcribe

B 这两段来自 SoulX-Podcast（Apache-2.0）：example/audios/
（上面这些 ref_text 就是用这个 transcribe 转出来的。）
