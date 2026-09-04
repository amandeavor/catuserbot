# Aetheris V5 Legacy Plugin Compatibility Audit

This audit systematically inspects and verifies every legacy plugin file in `userbot/plugins/`.

- **Total Plugins Audited**: 138
- **Syntax & AST Compilation**: 138 / 138 Passed
- **Total Commands Discovered**: 396
- **Total Watchers Discovered**: 8

## Plugin Compatibility Table

| Filename | Syntax/Import | Commands | Watchers | Telethon Deps | Unmanaged Tasks | External Imports | V5 Status |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| `account_powers.py` | PASS | 2 | 0 | 0 | 0 | asyncio, core.managers, time | SUPPORTED |
| `admin.py` | PASS | 12 | 0 | 5 | 0 | , contextlib, core.data (+5) | SUPPORTED |
| `admin_nuke_defense.py` | PASS | 3 | 0 | 1 | 0 | asyncio, core.managers | SUPPORTED |
| `aetheris_suite.py` | PASS | 3 | 0 | 2 | 0 | , Config, asyncio (+9) | SUPPORTED |
| `afk.py` | PASS | 4 | 0 | 1 | 0 | , Config, asyncio (+5) | SUPPORTED |
| `ai_powerhouse.py` | PASS | 8 | 0 | 0 | 0 | Config, aiohttp, core.managers (+6) | SUPPORTED |
| `aitools.py` | PASS | 2 | 0 | 0 | 0 | , core.managers, helpers (+2) | SUPPORTED |
| `alive.py` | PASS | 2 | 1 | 3 | 0 | , Config, core.managers (+9) | SUPPORTED |
| `android.py` | PASS | 4 | 0 | 0 | 0 | bs4, core.managers, json (+1) | SUPPORTED |
| `anilist.py` | PASS | 12 | 0 | 0 | 0 | aiohttp, bs4, contextlib (+14) | SUPPORTED |
| `antiflood.py` | PASS | 2 | 0 | 2 | 0 | , asyncio, sql_helper (+1) | SUPPORTED |
| `antispambot.py` | PASS | 2 | 1 | 4 | 0 | , Config, requests (+2) | SUPPORTED |
| `app.py` | PASS | 1 | 0 | 0 | 0 | , PIL, bs4 (+5) | SUPPORTED |
| `archive.py` | PASS | 4 | 0 | 2 | 4 | , Config, asyncio (+7) | SUPPORTED |
| `autoprofile.py` | PASS | 9 | 0 | 2 | 7 | , Config, PIL (+15) | SUPPORTED |
| `blacklistchats.py` | PASS | 4 | 0 | 1 | 0 | core.data, core.managers, datetime (+2) | SUPPORTED |
| `blacklistwords.py` | PASS | 4 | 0 | 1 | 0 | , core.managers, re (+2) | SUPPORTED |
| `broadcast.py` | PASS | 9 | 0 | 2 | 0 | , asyncio, base64 (+5) | SUPPORTED |
| `button.py` | PASS | 2 | 0 | 1 | 0 | , Config, helpers.functions.functions (+2) | SUPPORTED |
| `calc.py` | PASS | 1 | 0 | 0 | 0 | , io, sys (+1) | SUPPORTED |
| `carbon.py` | PASS | 6 | 0 | 0 | 0 | , asyncio, core.managers (+4) | SUPPORTED |
| `chain.py` | PASS | 1 | 0 | 1 | 0 | , core.managers | SUPPORTED |
| `channel_download.py` | PASS | 2 | 0 | 0 | 0 | , Config, contextlib (+3) | SUPPORTED |
| `chatbot.py` | PASS | 5 | 0 | 1 | 0 | core.managers, helpers, random (+2) | SUPPORTED |
| `climate.py` | PASS | 4 | 0 | 0 | 0 | , Config, aiohttp (+7) | SUPPORTED |
| `clone.py` | PASS | 2 | 0 | 2 | 0 | , Config, html (+1) | SUPPORTED |
| `collage.py` | PASS | 1 | 0 | 0 | 0 | core.managers, helpers, os | SUPPORTED |
| `corecmds.py` | PASS | 9 | 0 | 0 | 0 | , Config, contextlib (+5) | SUPPORTED |
| `create.py` | PASS | 1 | 0 | 1 | 0 | , Config, core.managers (+1) | SUPPORTED |
| `custom.py` | PASS | 2 | 0 | 0 | 0 | core.managers, sql_helper.globals, urlextract | SUPPORTED |
| `cyber_tools.py` | PASS | 5 | 0 | 0 | 0 | aiohttp, core.managers, json (+3) | SUPPORTED |
| `dictionary.py` | PASS | 2 | 0 | 0 | 0 | core.logger, core.managers, helpers (+1) | SUPPORTED |
| `direct_links.py` | PASS | 1 | 0 | 0 | 0 | bs4, core.logger, core.managers (+7) | SUPPORTED |
| `download.py` | PASS | 2 | 0 | 2 | 12 | Config, asyncio, core.managers (+9) | SUPPORTED |
| `download_modern.py` | PASS | 2 | 0 | 0 | 0 | asyncio, core.managers, glob (+5) | SUPPORTED |
| `emojigames.py` | PASS | 6 | 0 | 1 | 0 | , contextlib | SUPPORTED |
| `evaluators.py` | PASS | 3 | 0 | 0 | 0 | , asyncio, helpers.utils (+6) | SUPPORTED |
| `execmod.py` | PASS | 5 | 0 | 0 | 0 | core.managers, helpers.utils | SUPPORTED |
| `externalplugins.py` | PASS | 0 | 0 | 1 | 1 | , Config, helpers.utils (+3) | SUPPORTED |
| `fake.py` | PASS | 3 | 0 | 3 | 0 | , asyncio, core.managers (+2) | SUPPORTED |
| `fedutils.py` | PASS | 9 | 0 | 2 | 0 | Config, asyncio, contextlib (+4) | SUPPORTED |
| `ffmpeg.py` | PASS | 5 | 0 | 0 | 14 | Config, asyncio, contextlib (+8) | SUPPORTED |
| `fileconverts.py` | PASS | 10 | 0 | 4 | 6 | Config, PIL, asyncio (+12) | SUPPORTED |
| `filemanager.py` | PASS | 5 | 0 | 0 | 0 | , Config, asyncio (+7) | SUPPORTED |
| `filesummary.py` | PASS | 2 | 0 | 0 | 0 | , core.managers, helpers.tools (+3) | SUPPORTED |
| `filext.py` | PASS | 1 | 0 | 0 | 0 | bs4, core.managers, requests | SUPPORTED |
| `filters.py` | PASS | 5 | 0 | 1 | 0 | , core.managers, re (+1) | SUPPORTED |
| `forward.py` | PASS | 3 | 0 | 2 | 0 | Config, core.managers, string | SUPPORTED |
| `fryer.py` | PASS | 2 | 0 | 3 | 0 | PIL, core.managers, helpers.functions (+4) | SUPPORTED |
| `fun_modern.py` | PASS | 7 | 0 | 0 | 0 | aiohttp, core.managers, io (+1) | SUPPORTED |
| `gadmin.py` | PASS | 7 | 0 | 4 | 0 | , asyncio, contextlib (+5) | SUPPORTED |
| `gdrive.py` | PASS | 10 | 0 | 2 | 4 | , Config, asyncio (+26) | SUPPORTED |
| `getid.py` | PASS | 1 | 0 | 1 | 0 | core.managers | SUPPORTED |
| `gifs.py` | PASS | 1 | 0 | 0 | 0 | , core.managers, helpers (+2) | SUPPORTED |
| `git.py` | PASS | 3 | 0 | 0 | 0 | , Config, aiohttp (+8) | SUPPORTED |
| `glitch.py` | PASS | 1 | 0 | 0 | 0 | PIL, core.managers, glitch_this (+2) | SUPPORTED |
| `google.py` | PASS | 5 | 0 | 0 | 0 | core.managers, datetime, helpers.functions (+6) | SUPPORTED |
| `gps.py` | PASS | 1 | 0 | 1 | 0 | core.managers, geopy.geocoders, helpers | SUPPORTED |
| `greetings.py` | PASS | 17 | 0 | 0 | 0 | , core.managers, random | SUPPORTED |
| `groupactions.py` | PASS | 6 | 0 | 5 | 0 | , asyncio, contextlib (+4) | SUPPORTED |
| `groupdata.py` | PASS | 5 | 0 | 4 | 0 | , core.logger, core.managers (+8) | SUPPORTED |
| `hash.py` | PASS | 2 | 0 | 0 | 2 | Config, asyncio, base64 (+6) | SUPPORTED |
| `help.py` | PASS | 4 | 0 | 1 | 0 | Config, core, core.cmdinfo (+2) | SUPPORTED |
| `heroku.py` | PASS | 4 | 0 | 0 | 0 | Config, core.managers, helpers (+5) | SUPPORTED |
| `hikka_resilience.py` | PASS | 5 | 0 | 1 | 0 | aiohttp, asyncio, core.managers (+3) | SUPPORTED |
| `image_magic.py` | PASS | 1 | 0 | 0 | 0 | PIL, asyncio, core.managers (+3) | SUPPORTED |
| `images.py` | PASS | 1 | 0 | 1 | 0 | contextlib, core.managers, helpers.google_image_download (+3) | SUPPORTED |
| `invite.py` | PASS | 1 | 0 | 1 | 0 | core.managers | SUPPORTED |
| `json.py` | PASS | 2 | 0 | 0 | 0 | core.managers, helpers.utils | SUPPORTED |
| `lastfm.py` | PASS | 3 | 0 | 4 | 0 | , Config, asyncio (+7) | SUPPORTED |
| `letmesearch.py` | PASS | 10 | 0 | 0 | 0 | asyncio, core.managers | SUPPORTED |
| `locks.py` | PASS | 7 | 1 | 5 | 0 | , base64, contextlib (+5) | SUPPORTED |
| `logchats.py` | PASS | 7 | 0 | 0 | 0 | , Config, afk (+6) | SUPPORTED |
| `logo.py` | PASS | 4 | 0 | 0 | 0 | , PIL, bs4 (+9) | SUPPORTED |
| `lyrics.py` | PASS | 1 | 0 | 0 | 0 | , Config, core.managers (+1) | SUPPORTED |
| `markdown.py` | PASS | 2 | 0 | 6 | 0 | functools, random, re | SUPPORTED |
| `mediainfo.py` | PASS | 1 | 0 | 0 | 0 | Config, contextlib, core.managers (+3) | SUPPORTED |
| `mega.py` | PASS | 1 | 0 | 0 | 0 | , Config, asyncio (+11) | SUPPORTED |
| `memify.py` | PASS | 11 | 0 | 1 | 0 | PIL, asyncio, base64 (+10) | SUPPORTED |
| `mention.py` | PASS | 3 | 0 | 1 | 0 | helpers.utils | SUPPORTED |
| `notebook.py` | PASS | 3 | 0 | 1 | 0 | , Config, core.managers (+5) | SUPPORTED |
| `nsfwdetect.py` | PASS | 1 | 0 | 0 | 0 | Config, core.managers, os (+1) | SUPPORTED |
| `ocr.py` | PASS | 2 | 0 | 0 | 0 | , Config, core.managers (+5) | SUPPORTED |
| `openai.py` | PASS | 2 | 0 | 0 | 0 | core.managers, helpers.chatbot, helpers.utils (+2) | SUPPORTED |
| `pastebin.py` | PASS | 6 | 0 | 2 | 0 | , Config, core.events (+14) | SUPPORTED |
| `ping.py` | PASS | 1 | 0 | 1 | 0 | , Config, asyncio (+7) | SUPPORTED |
| `pmpermit.py` | PASS | 10 | 5 | 3 | 0 | , Config, core.managers (+6) | SUPPORTED |
| `poll.py` | PASS | 1 | 0 | 3 | 0 | , core.managers, random | SUPPORTED |
| `poto.py` | PASS | 2 | 0 | 0 | 0 | , PIL, core.managers | SUPPORTED |
| `powertools.py` | PASS | 4 | 0 | 0 | 0 | , asyncio.exceptions, core.logger (+5) | SUPPORTED |
| `privatewelcome.py` | PASS | 3 | 1 | 2 | 0 | , asyncio, core.managers (+2) | SUPPORTED |
| `profile.py` | PASS | 7 | 0 | 6 | 0 | Config, core.logger, core.managers (+1) | SUPPORTED |
| `purge.py` | PASS | 6 | 0 | 2 | 0 | , asyncio, core.managers (+2) | SUPPORTED |
| `quotly.py` | PASS | 3 | 0 | 3 | 0 | PIL, core.logger, core.managers (+7) | SUPPORTED |
| `reddit.py` | PASS | 1 | 0 | 0 | 0 | , core.logger, core.managers (+3) | SUPPORTED |
| `removebg.py` | PASS | 1 | 0 | 0 | 0 | Config, core.managers, helpers.utils (+2) | SUPPORTED |
| `rename.py` | PASS | 1 | 0 | 0 | 4 | , Config, asyncio (+5) | SUPPORTED |
| `sangmata.py` | PASS | 1 | 0 | 3 | 0 | asyncio, core.managers, helpers (+1) | SUPPORTED |
| `schedule.py` | PASS | 3 | 0 | 0 | 0 | apscheduler.schedulers.asyncio, contextlib, core.managers (+3) | SUPPORTED |
| `scrapers.py` | PASS | 2 | 0 | 0 | 0 | , bs4, core.managers (+6) | SUPPORTED |
| `screenshot.py` | PASS | 2 | 0 | 0 | 0 | Config, core.managers, datetime (+5) | SUPPORTED |
| `sed.py` | PASS | 1 | 2 | 2 | 0 | Config, collections, core.managers (+1) | SUPPORTED |
| `selfdestruct.py` | PASS | 2 | 0 | 0 | 0 | asyncio | SUPPORTED |
| `snip.py` | PASS | 4 | 0 | 0 | 0 | , contextlib, core.managers (+2) | SUPPORTED |
| `social_fun.py` | PASS | 5 | 0 | 0 | 0 | asyncio, core.managers, random | SUPPORTED |
| `songs.py` | PASS | 4 | 0 | 4 | 0 | , ShazamAPI, base64 (+9) | SUPPORTED |
| `spam.py` | PASS | 6 | 0 | 5 | 0 | , asyncio, base64 (+4) | SUPPORTED |
| `speedtest.py` | PASS | 1 | 0 | 0 | 0 | core.managers, helpers.utils, speedtest (+1) | SUPPORTED |
| `spotify.py` | PASS | 6 | 0 | 6 | 0 | , Config, PIL (+13) | SUPPORTED |
| `stats.py` | PASS | 3 | 0 | 4 | 0 | , asyncio, contextlib (+3) | SUPPORTED |
| `stealth_channel_save.py` | PASS | 1 | 0 | 0 | 0 | asyncio, core.managers | SUPPORTED |
| `stickerfun.py` | PASS | 10 | 0 | 0 | 0 | PIL, core.managers, helpers.functions (+7) | SUPPORTED |
| `stickers.py` | PASS | 6 | 0 | 6 | 0 | PIL, asyncio, base64 (+15) | SUPPORTED |
| `stt.py` | PASS | 1 | 0 | 0 | 0 | Config, core.managers, datetime (+3) | SUPPORTED |
| `sudo.py` | PASS | 7 | 0 | 1 | 1 | Config, core, core.data (+6) | SUPPORTED |
| `sysdetails.py` | PASS | 3 | 0 | 1 | 0 | core.managers, datetime, helpers.utils (+3) | SUPPORTED |
| `tadmin.py` | PASS | 2 | 0 | 5 | 0 | , core.managers, helpers.utils | SUPPORTED |
| `telegraph.py` | PASS | 2 | 0 | 3 | 0 | , Config, PIL (+9) | SUPPORTED |
| `thumbnail.py` | PASS | 3 | 0 | 0 | 0 | Config, PIL, core.managers (+4) | SUPPORTED |
| `time.py` | PASS | 2 | 0 | 0 | 0 | , Config, PIL (+4) | SUPPORTED |
| `tools.py` | PASS | 10 | 0 | 2 | 0 | Config, PIL, barcode (+15) | SUPPORTED |
| `transfer_channel.py` | PASS | 1 | 0 | 2 | 0 | Config | SUPPORTED |
| `translate.py` | PASS | 3 | 0 | 0 | 0 | , core.managers, googletrans (+2) | SUPPORTED |
| `trolls.py` | PASS | 4 | 0 | 0 | 0 | , core.managers, helpers (+2) | SUPPORTED |
| `tts.py` | PASS | 1 | 0 | 0 | 0 | , core.managers, datetime (+3) | SUPPORTED |
| `ultroid_power.py` | PASS | 7 | 0 | 0 | 0 | aiohttp, base64, core.managers (+3) | SUPPORTED |
| `updater.py` | PASS | 3 | 0 | 0 | 0 | Config, asyncio, asyncio.exceptions (+11) | SUPPORTED |
| `upload.py` | PASS | 1 | 0 | 2 | 2 | Config, asyncio, core.managers (+10) | SUPPORTED |
| `urltools.py` | PASS | 4 | 0 | 0 | 0 | core.managers, requests, validators.url | SUPPORTED |
| `voice_magic.py` | PASS | 1 | 0 | 0 | 0 | asyncio, core.managers, io (+3) | SUPPORTED |
| `vps.py` | PASS | 2 | 0 | 0 | 0 | core.managers, glob, helpers (+4) | SUPPORTED |
| `wall.py` | PASS | 1 | 0 | 0 | 0 | bs4, core.logger, core.managers (+5) | SUPPORTED |
| `warns.py` | PASS | 3 | 0 | 0 | 0 | core.managers, html, sql_helper | SUPPORTED |
| `watch.py` | PASS | 1 | 0 | 0 | 0 | Config, core.logger, core.managers (+3) | SUPPORTED |
| `webupload.py` | PASS | 2 | 0 | 0 | 0 | Config, asyncio, core.managers (+5) | SUPPORTED |
| `welcome.py` | PASS | 4 | 1 | 2 | 0 | , core.managers, sql_helper.globals (+1) | SUPPORTED |
| `whois.py` | PASS | 3 | 0 | 2 | 0 | , Config, contextlib (+5) | SUPPORTED |
| `ytdl.py` | PASS | 4 | 0 | 4 | 4 | , Config, asyncio (+16) | SUPPORTED |

## Unmanaged Task Analysis
The following plugins contain direct `loop.create_task` or `asyncio.create_task` invocations:

### `archive.py`
- `event.client.fast_download_file(location=reply.document, out`
- `event.client.fast_download_file(location=reply.document, out`
- `asyncio.get_event_loop().create_task(progress(d, t, mone, c_`
- `asyncio.get_event_loop().create_task(progress(d, t, mone, c_`

### `autoprofile.py`
- `catub.loop.create_task(autopfp_start())`
- `catub.loop.create_task(autopicloop())`
- `catub.loop.create_task(digitalpicloop())`
- `catub.loop.create_task(bloom_pfploop())`
- `catub.loop.create_task(autoname_loop())`
- `catub.loop.create_task(autobio_loop())`
- `catub.loop.create_task(custompfploop())`

### `download.py`
- `reply.download_media(file=file_name.absolute(), progress_cal`
- `reply.download_media(file=file_name.absolute(), progress_cal`
- `reply.download_media(file=location, progress_callback=lambda`
- `event.client.fast_download_file(location=reply.document, out`
- `reply.download_media(file=downloads, progress_callback=lambd`
- `event.client.fast_download_file(location=reply.document, out`
- `asyncio.get_event_loop().create_task(progress(d, t, mone, c_`
- `asyncio.get_event_loop().create_task(progress(d, t, mone, c_`
- `asyncio.get_event_loop().create_task(progress(d, t, mone, c_`
- `asyncio.get_event_loop().create_task(progress(d, t, mone, c_`
- `asyncio.get_event_loop().create_task(progress(d, t, mone, c_`
- `asyncio.get_event_loop().create_task(progress(d, t, mone, c_`

### `externalplugins.py`
- `catub.loop.create_task(install())`

### `ffmpeg.py`
- `event.client.send_file(event.chat_id, o, caption=' '.join(cm`
- `event.client.fast_download_file(location=reply_message.docum`
- `event.client.send_file(event.chat_id, compress, thumb=thumb_`
- `event.client.send_file(event.chat_id, compress, caption=cap,`
- `event.client.send_file(event.chat_id, o, caption=' '.join(cm`
- `event.client.fast_download_file(location=reply_message.docum`
- `event.client.send_file(event.chat_id, o, caption=' '.join(cm`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`

### `fileconverts.py`
- `event.client.download_media(reply_message, Config.TMP_DOWNLO`
- `event.client.fast_upload_file(file=ul, progress_callback=lam`
- `event.client.send_file(entity=event.chat_id, file=new_requir`
- `asyncio.get_event_loop().create_task(progress(d, t, event, c`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, event, c`

### `gdrive.py`
- `event.client.send_file(event.chat_id, file_name, caption=f'*`
- `event.client.download_media(await event.get_reply_message(),`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, gdrive, `

### `hash.py`
- `event.client.download_media(reply, Config.TMP_DOWNLOAD_DIREC`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`

### `rename.py`
- `event.client.download_media(reply_message, downloaded_file_n`
- `event.client.send_file(event.chat_id, downloaded_file_name, `
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, event, c`

### `sudo.py`
- `catub.loop.create_task(_init())`

### `upload.py`
- `event.client.fast_upload_file(file=ul, progress_callback=lam`
- `asyncio.get_event_loop().create_task(progress(d, t, event, c`

### `ytdl.py`
- `event.client.fast_upload_file(file=ul, progress_callback=lam`
- `event.client.fast_upload_file(file=ul, progress_callback=lam`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`
- `asyncio.get_event_loop().create_task(progress(d, t, catevent`

