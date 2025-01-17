# -*- coding: utf-8 -*-

import asyncio,shlex,logging,time,os,aiohttp,shutil
import orjson as json
from telethon.hints import MessageLike
from telethon.tl.types import KeyboardButtonCallback
from typing import Union,List,Tuple,Dict,Optional
from ..functions.Human_Format import human_readable_bytes
from ..functions.tele_upload import upload_handel
from ..core.getVars import get_val
from PIL import Image

torlog = logging.getLogger(__name__)

# attempt to decorate error prone areas
import traceback
def skipTorExp(func):
    def wrap_func(*args,**kwargs):
        try:
            return func(*args,**kwargs)
        except Exception as e:
            torlog.error(e)
            return
    return wrap_func

async def cli_call(cmd: Union[str,List[str]]) -> Tuple[str,str]:
    if isinstance(cmd,str):
        cmd = shlex.split(cmd)
    elif isinstance(cmd,(list,tuple)):
        pass
    else:
        return None,None
    
    process = await asyncio.create_subprocess_exec(
        *cmd,
        stderr=asyncio.subprocess.PIPE,
        stdout=asyncio.subprocess.PIPE
    )

    stdout, stderr = await process.communicate()
    
    stdout = stdout.decode().strip()
    stderr = stderr.decode().strip()

    with open("test.txt","w",encoding="UTF-8") as f:
        f.write(stdout)
    
    return stdout, stderr


async def get_yt_link_details(url: str) -> Union[Dict[str,str], None]:
    cmd = "youtube-dl --no-warnings --youtube-skip-dash-manifest --dump-json"
    cmd = shlex.split(cmd)
    if "hotstar" in url:
        cmd.append("--geo-bypass-country")
        cmd.append("IN")
    cmd.append(url)
    
    out, error = await cli_call(cmd)
    if error:
        torlog.error(f"Error occured:- {error} for url {url}")
    
    try:
        return json.loads(out), None
    except:
        torlog.exception("Error occured while parsing the json.\n")
        return None, error

async def get_max_thumb(data: dict, suid: str) -> str:
    thumbnail = data.get("thumbnail")
    thumb_path = None

    # alot of context management XD
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(thumbnail) as resp:
                thumb_path = os.path.join(os.getcwd(),"userdata")
                if not os.path.exists(thumb_path):
                    os.mkdir(thumb_path)

                thumb_path = os.path.join(thumb_path,f"{suid}.webp")
                with open(thumb_path,"wb") as ifile:
                    ifile.write(await resp.read())

        Image.open(thumb_path).convert("RGB").save(thumb_path)

        return thumb_path
    except:
        torlog.exception("Error in thumb gen")
        return None

async def create_quality_menu(url: str,message: MessageLike, message1: MessageLike,jsons: Optional[str] = None, suid: Optional[str] = None):
    if jsons is None:
        data, err = await get_yt_link_details(url)
        suid = str(time.time()).replace(".","")
    else:
        data = jsons

    with open("test.txt","w") as f:
        f.write(json.dumps(data).decode("UTF-8"))

    if data is None:
        await message.edit("Errored failed parsing.")
        return None, err
    else:
        unique_formats = dict()
        for i in data.get("formats"):
            c_format = i.get("format_note")
            if c_format is None:
                c_format = i.get("height")
            if not c_format in unique_formats:
                if i.get("filesize") is not None:
                    unique_formats[c_format] = [i.get("filesize"),i.get("filesize")]
                else:
                    unique_formats[c_format] = [0,0]

            else:
                if i.get("filesize") is not None:
                    if unique_formats[c_format][0] > i.get("filesize"):
                        unique_formats[c_format][0] = i.get("filesize")
                    else:
                        unique_formats[c_format][1] = i.get("filesize")

        buttons = list()
        for i in unique_formats.keys():
            
            # add human bytes here
            if i == "tiny":
                text = f"tiny [{human_readable_bytes(unique_formats[i][0])} - {human_readable_bytes(unique_formats[i][1])}] ➡️"
                cdata = f"ytdlsmenu|{i}|{message1.sender_id}|{suid}" # add user id
            else:
                text = f"{i} [{human_readable_bytes(unique_formats[i][0])} - {human_readable_bytes(unique_formats[i][1])}] ➡️"
                cdata = f"ytdlsmenu|{i}|{message1.sender_id}|{suid}" # add user id
            buttons.append([KeyboardButtonCallback(text,cdata.encode("UTF-8"))])
        buttons.append([KeyboardButtonCallback("Audios ➡️",f"ytdlsmenu|audios|{message1.sender_id}|{suid}")])
        await message.edit("Choose a quality/option available below.",buttons=buttons)
        
        if jsons is None:
            path = os.path.join(os.getcwd(),'userdata')
            
            if not os.path.exists(path):
                os.mkdir(path)
            
            path = os.path.join(path,f"{suid}.json")
            
            with open(path,"w",encoding="UTF-8") as file:
                file.write(json.dumps(data).decode("UTF-8"))



    return True
        
async def handle_ytdl_command(e: MessageLike):
    if not e.is_reply:
        await e.reply("Reply to a youtube video link.")
        return
    msg = await e.get_reply_message()
    msg1 = await e.reply("Processing the link...")
    if msg.text.find("http") != -1:
        res, err = await create_quality_menu(msg.text.strip(),msg1,msg)
        if res is None:
            await msg1.edit(f"<code>Invalid link provided.\n{err}</code>",parse_mode="html")
    else:
        await e.reply("Invalid link provided.")

async def handle_ytdl_callbacks(e: MessageLike):
    data = e.data.decode("UTF-8")
    data = data.split("|")
    
    if data[0] == "ytdlsmenu":
        if data[2] != str(e.sender_id):
            await e.answer("Not valid user, Dont touch.")
            return
        
        path = os.path.join(os.getcwd(),'userdata',data[3]+".json")
        if os.path.exists(path):
            with open(path) as file:
                ytdata = json.loads(file.read())
                buttons = list()
                if data[1] == "audios":
                    for i in ["64K","128K","320K"]:
                        text = f"{i} [MP3]"
                        cdata = f"ytdldfile|{i}|{e.sender_id}|{data[3]}"
                        buttons.append([KeyboardButtonCallback(text,cdata.encode("UTF-8"))])
                else:
                    j = 0
                    for i in ytdata.get("formats"):
                        c_format = i.get("format_note")
                        format_id = i.get('format_id')
                        height = i.get('format')
                        if c_format is None:
                            c_format = str(i.get("height"))
                            format_id = f"xxother{j}"
                            height = i.get('format')
                        if not c_format == data[1]:
                            continue
                        
                        
                        if not height:
                            continue
                            
                        text = f"{height} [{i.get('ext')}] [{human_readable_bytes(i.get('filesize'))}]"
                        cdata = f"ytdldfile|{format_id}|{e.sender_id}|{data[3]}"
                        
                        buttons.append([KeyboardButtonCallback(text,cdata.encode("UTF-8"))])
                        j+=1
                
                buttons.append([KeyboardButtonCallback("Go Back 😒",f"ytdlmmenu|{data[2]}|{data[3]}")])
                await e.edit(f"Files for quality {data[1]}",buttons=buttons)
                


        else:
            await e.answer("Try again something went wrong.",alert=True)
            await e.delete()
    elif data[0] == "ytdlmmenu":
        if data[1] != str(e.sender_id):
            await e.answer("Not valid user, Dont touch.")
            return
        path = os.path.join(os.getcwd(),'userdata',data[2]+".json")
        if os.path.exists(path):
            with open(path,encoding="UTF-8") as file:
                ytdata = json.loads(file.read())
                await create_quality_menu("",await e.get_message(),e,ytdata,data[2])

        else:
            await e.answer("Try again something went wrong.",alert=True)
            await e.delete()

async def handle_ytdl_file_download(e: MessageLike):
    # ytdldfile | format_id | sender_id | suid | is_audio

    data = e.data.decode("UTF-8")
    data = data.split("|")
    
    
    if data[2] != str(e.sender_id):
        await e.answer("Not valid user, Dont touch.")
        return
    else:
        await e.answer("Crunching Data.....")
    
    await e.edit(buttons=None)

    is_audio = False

    path = os.path.join(os.getcwd(),'userdata',data[3]+".json")
    if os.path.exists(path):
        with open(path,encoding="UTF-8") as file:
            ytdata = json.loads(file.read())
            yt_url = ytdata.get("webpage_url")
            thumb_path = await get_max_thumb(ytdata,data[3])

            op_dir = os.path.join(os.getcwd(),'userdata',data[3])
            if not os.path.exists(op_dir):
                os.mkdir(op_dir)
            if data[1].startswith("xxother"):
                data[1] = data[1].replace("xxother","")
                data[1] = int(data[1])
                j = 0
                for i in ytdata.get("formats"):
                    if j == data[1]:
                        data[1] = i.get("format_id")
                    j +=1
            else:
                for i in ytdata.get("formats"):
                    if i.get("format_id") == data[1]:
                        if i.get("acodec") is not None:
                            is_audio = True
                            
                    
            if data[1].endswith("K"):
                cmd = f"youtube-dl -i --extract-audio --add-metadata --audio-format mp3 --audio-quality {data[1]} -o '{op_dir}/%(title)s.%(ext)s' {yt_url}"

            else:
                if is_audio:
                    cmd = f"youtube-dl --continue --embed-subs --no-warnings --hls-prefer-ffmpeg --prefer-ffmpeg -f {data[1]} -o {op_dir}/%(title)s.%(ext)s {yt_url}"
                else:
                    cmd = f"youtube-dl --continue --embed-subs --no-warnings --hls-prefer-ffmpeg --prefer-ffmpeg -f {data[1]}+bestaudio[ext=m4a]/best -o {op_dir}/%(title)s.%(ext)s {yt_url}"
            
            out, err = await cli_call(cmd)
            
            if not err:
                
                # TODO Fix the original thumbnail
                # rdict = await upload_handel(op_dir,await e.get_message(),e.sender_id,dict(),thumb_path=thumb_path)
                
                rdict = await upload_handel(op_dir,await e.get_message(),e.sender_id,dict(), user_msg=e)
                await print_files(e,rdict)
                
                shutil.rmtree(op_dir)
                os.remove(thumb_path)
                os.remove(path)
            else:
                torlog.error(err)
                omess = await e.get_message()
                omess1 = await omess.get_reply_message()
                if "HTTP Error 429" in err:
                    emsg = "HTTP Error 429: Too many requests try after a while."
                else:
                    emsg = "An error has occured trying to upload any files that are found here."
                await omess.edit(emsg)
                if omess1 is None:
                    await omess.respond(emsg)
                else:
                    await omess1.reply(emsg)
                
                rdict = await upload_handel(op_dir,await e.get_message(),e.sender_id,dict(), user_msg=e)
                await print_files(e,rdict)

                try:
                    shutil.rmtree(op_dir)
                    os.remove(thumb_path)
                    os.remove(path)
                except:
                    pass

    else:
        await e.delete()
        await e.answer("Try again something went wrong.",alert=True)
        await e.delete()

async def handle_ytdl_playlist(e: MessageLike) -> None:
    if not e.is_reply:
        await e.reply("Reply to a youtube playlist link.")
        return
    url = await e.get_reply_message()
    url = url.text.strip()
    cmd = f"youtube-dl -i --flat-playlist --dump-single-json {url}"
    
    msg = await e.reply("Processing your Youtube Playlist download request")

    # cancel the playlist if time exceed 5 mins
    try:
        out, err = await asyncio.wait_for(cli_call(cmd),300)
    except asyncio.TimeoutError:
        await msg.edit("Error: The playlist contains too many videos to handle")
        return
    
    if err:
        await msg.edit(f"Failed to load the playlist with the error:- <code>{err}</code>",parse_mode="html")
        return
    

    try:
        pldata = json.loads(out)
        entities = pldata.get("entries")
        if len(entities) <= 0:
            await msg.edit("Cannot load the videos from this playlist ensure that the playlist is not <code>'My Mix or Mix'</code>. It should be a public or unlisted youtube playlist.")
            return

        entlen = len(entities)
        keybr = list()
        
        # limit the max vids
        if entlen > get_val("MAX_YTPLAYLIST_SIZE"):

            await msg.edit(f"Playlist too large max {get_val('MAX_YTPLAYLIST_SIZE')} vids allowed as of now. This has {entlen}")
            return


        # format> ytdlplaylist | quality | suid | sender_id
        suid = str(time.time()).replace(".","")

        for i in ["144","240","360","480","720","1080","1440","2160"]:
            keybr.append([KeyboardButtonCallback(text=f"{i}p All videos",data=f"ytdlplaylist|{i}|{suid}|{e.sender_id}")])

        keybr.append([KeyboardButtonCallback(text=f"Best All videos",data=f"ytdlplaylist|best|{suid}|{e.sender_id}")])
        
        
        keybr.append([KeyboardButtonCallback(text="Best all audio only. [340k]",data=f"ytdlplaylist|320k|{suid}|{e.sender_id}")])
        keybr.append([KeyboardButtonCallback(text="Medium all audio only. [128k]",data=f"ytdlplaylist|128k|{suid}|{e.sender_id}")])
        keybr.append([KeyboardButtonCallback(text="Worst all audio only. [64k]",data=f"ytdlplaylist|64k|{suid}|{e.sender_id}")])

        await msg.edit(f"Found {entlen} videos in the playlist.",buttons=keybr) 

        path = os.path.join(os.getcwd(),'userdata')
        
        if not os.path.exists(path):
            os.mkdir(path)
        
        path = os.path.join(path,f"{suid}.json")
        
        with open(path,"w",encoding="UTF-8") as file:
            file.write(json.dumps(pldata).decode("UTF-8"))

    except:
        await msg.edit("Failed to parse the playlist. Check log if you think its error.")
        torlog.exception("Playlist Parse failed") 

async def handle_ytdl_playlist_down(e: MessageLike) -> None:
    # ytdlplaylist | quality | suid | sender_id
    
    data = e.data.decode("UTF-8").split("|")
    
    if data[3] != str(e.sender_id):
        await e.answer("Not valid user, Dont touch.")
        return
    else:
        await e.answer("Crunching Data...")

    await e.edit(buttons=None)
    path = os.path.join(os.getcwd(),"userdata",data[2]+".json")
    if os.path.exists(path):
        await e.answer("Processing, please wait")
        opdir = os.path.join(os.getcwd(),"userdata",data[2])
        if not os.path.exists(opdir):
            os.mkdir(opdir)

        with open(path) as file:
            pldata = json.loads(file.read())
        url = pldata.get("webpage_url")

        if data[1].endswith("k"):
            audcmd = f"youtube-dl -i --extract-audio --add-metadata --audio-format mp3 --audio-quality {data[1]} -o '{opdir}/%(playlist_index)s - %(title)s.%(ext)s' {url}"
            out, err = await cli_call(audcmd)
            if err:
                await e.reply(f"Failed to download the audios <code>{err}</code>",parse_mode="html")
            else:
                rdict = await upload_handel(opdir, await e.get_message(), e.sender_id, dict(), user_msg=e)
                await print_files(e,rdict)
        else:
            if data[1] == "best":
                vidcmd = f"youtube-dl --continue --embed-subs --no-warnings --prefer-ffmpeg -f 'bestvideo[ext=mp4]+bestaudio[ext=m4a]/best' -o '{opdir}/%(playlist_index)s - %(title)s.%(ext)s' {url}"
            else:
                vidcmd = f"youtube-dl --continue --embed-subs --no-warnings --prefer-ffmpeg -f 'bestvideo[ext=mp4,height<={data[1]}]+bestaudio[ext=m4a]/best' -o '{opdir}/%(playlist_index)s - %(title)s.%(ext)s' {url}"
            out, err = await cli_call(vidcmd)
            if err:
                await e.reply(f"Failed to download the videos <code>{err}</code>",parse_mode="html")
            else:
                rdict = await upload_handel(opdir, await e.get_message(), e.sender_id, dict(), user_msg=e)
                await print_files(e,rdict)
        shutil.rmtree(opdir)
        os.remove(path)
    else:
        await e.delete()
        await e.answer("Something went wrong try again.",alert=True)
        torlog.error("the file for that suid was not found.")

async def print_files(e,files):
    
    msg = "#botuploads\n"
    if len(files) == 0:
        return
    
    chat_id = e.chat_id

    for i in files.keys():
        link = f'https://t.me/c/{str(chat_id)[4:]}/{files[i]}'
        msg += f'🚩 <a href="{link}">{i}</a>\n'
     
    rmsg = await e.client.get_messages(e.chat_id,ids=e.message_id)
    rmsg = await rmsg.get_reply_message()
    if rmsg is None:
        #msg += "\n<a href='tg://user?id={}'>Done<a>".format(rmsg.sender_id)
        msg += "\n<a href='tg://user?id={}'>Done</a>".format(e.sender_id)
        await e.reply(msg,parse_mode="html")
    else:
        msg += "\n<a href='tg://user?id={}'>Done</a>".format(rmsg.sender_id)
        await rmsg.reply(msg,parse_mode="html")

    if len(files) < 2:
        return

    ids = list()
    for i in files.keys():
        ids.append(files[i])
    
    msgs = await e.client.get_messages(e.chat_id,ids=ids)
    for i in msgs:
        index = None
        for j in range(0,len(msgs)):
            index = j
            if ids[j] == i.id:
                break
        nextt,prev = "",""
        chat_id = str(e.chat_id)[4:]
        if index == 0:
            nextt = f'https://t.me/c/{chat_id}/{ids[index+1]}'
            nextt = f'<a href="{nextt}">Next</a>\n'
        elif index == len(msgs)-1:
            prev = f'https://t.me/c/{chat_id}/{ids[index-1]}'
            prev = f'<a href="{prev}">Prev</a>\n'
        else:
            nextt = f'https://t.me/c/{chat_id}/{ids[index+1]}'
            nextt = f'<a href="{nextt}">Next</a>\n'
            
            prev = f'https://t.me/c/{chat_id}/{ids[index-1]}'
            prev = f'<a href="{prev}">Prev</a>\n'

        try:
            await i.edit("{} {} {}".format(prev,i.text,nextt),parse_mode="html")
        except:pass
        await asyncio.sleep(1)

#todo
# Add the YT playlist feature here
# Add the YT channels feature here 