"""Render an HD narrated tutorial from offscreen app views and vector graphics.
Requires Pillow, PySide6 and PyAV. Never captures the desktop or opens audio devices.
Run --assets, tools/narrate_tutorial.ps1, then --render.
"""
import argparse,json,math,os,textwrap,wave
from fractions import Fraction
from pathlib import Path
import numpy as np
from PIL import Image,ImageDraw,ImageFont

ROOT=Path(__file__).resolve().parents[1]
OUT=ROOT/'artifacts/tutorial'
SCENES=[
 dict(title='Your voice.\nA safer stream.',label='STREAMGUARD / QUICK START',kind='hero',
      tip='English release candidate  |  0.3 RC1',
      narration='Welcome to StreamGuard. This guide shows how to record a full session, use live filtering, and safely change your blocked words. The interface examples use demonstration data. This release supports English.'),
 dict(title='Choose a mode.\nWe match the model.',label='01 / TWO SIMPLE WORKFLOWS',kind='modes',
      tip='Record first, or filter live. Switch while stopped.',
      narration='Open Launch StreamGuard in your project folder. Choose your test mode. Recording uses local Whisper when installed. Live protection uses fast Vosk. Switching modes now restores the matching detector and its model folder automatically.'),
 dict(title='Record the\nwhole session.',label='02 / RECORD AND REVIEW',kind='record',
      tip='Start recording → speak → Stop → wait for processing',
      narration='For a full recording, select your microphone and click Start recording. Speak normally, then click Stop. Wait while StreamGuard filters the entire file. Play original and Play filtered let you compare the results. Open recordings shows the saved files.'),
 dict(title='Go live with\na short buffer.',label='03 / LIVE FILTERING',kind='live',
      tip='Start protection. Wait for FILTERING.',
      narration='For live mode, choose your microphone and output device. Start with one point two five seconds of audience delay or more. Click Start protection and wait for Filtering. Only the audience path is delayed. Use headphones for listening tests to avoid microphone feedback.'),
 dict(title='Know when\na word is caught.',label='04 / ON-SCREEN FEEDBACK',kind='notice',
      tip='Notice + event log + optional live recording',
      narration='When a blocked word is detected, an on-screen notice and event entry appear. Save live output records what the output actually received, including startup or protective silence. If you see Protection at risk, review the message and test with a larger buffer before broadcasting.'),
 dict(title='Edit. Validate.\nStart again.',label='05 / CHANGE BLOCKED WORDS',kind='words',
      tip='Stop → edit one word per line → Save settings → Start',
      narration='To change the list, stop the current session first. Enter one English word per line and click Save settings. Wait for Settings validated and saved. Then start again. Every new session uses a fresh detector and the updated word list.'),
 dict(title='Unsupported word?\nFix it here.',label='06 / CLEAR, RECOVERABLE ERRORS',kind='unsupported',
      tip='No words are silently skipped.',
      narration='Some custom words are outside the English live model vocabulary. StreamGuard names them and keeps your last valid saved settings. Edit those entries, or click Remove unsupported words. Save again, then restart. Hindi and Hinglish support is not included in this release.'),
 dict(title='Switch modes.\nKeep your settings.',label='07 / REPEAT WITHOUT RESTARTING',kind='switch',
      tip='Wait until STOPPED before changing the mode.',
      narration='To move between live and recording, click Stop and wait until processing finishes. Change the test mode and click its Start button. Model folders and playback results are remembered separately. If startup fails, correct the visible issue and try again. Reopening the launcher brings back the existing app.'),
 dict(title='Connect to OBS\nwhen ready.',label='08 / BROADCAST ROUTING',kind='obs',
      tip='Test a local OBS recording before going live.',
      narration='For OBS, install a virtual audio cable. Send StreamGuard to CABLE Input, and capture CABLE Output in OBS. Disable the raw microphone source. Match the video delay to the measured audio delay and check a local recording. Speech recognition can still miss words, so verify your own voice and setup.'),
 dict(title='You are ready\nto test.',label='STREAMGUARD / YOUR CHECKLIST',kind='end',
      tip='Launch StreamGuard.cmd  •  English  •  Local processing',
      narration='Start with a full recording. Compare original and filtered audio. Then test live filtering, a word-list edit, and a mode switch. Keep your recordings for review. Your speech stays local. These fixes improve session reliability, while broadcast readiness still depends on testing your real setup.')
]


def assets():
    os.environ['QT_QPA_PLATFORM']='offscreen'
    from PySide6.QtWidgets import QApplication
    from PySide6.QtCore import QPoint
    from PySide6.QtGui import QFontDatabase
    import streamguard.ui.main_window as ui
    from streamguard.detection.vocabulary import UnsupportedWordsError
    ui.devices=lambda:[{'id':1,'name':'Your microphone','host':'Windows DirectSound','input_channels':1,'output_channels':0},
        {'id':2,'name':'CABLE Input','host':'Windows DirectSound','input_channels':0,'output_channels':2}]
    app=QApplication([])
    for name in ('segoeui.ttf','segoeuib.ttf'):QFontDatabase.addApplicationFont('C:/Windows/Fonts/'+name)
    OUT.mkdir(parents=True,exist_ok=True)
    for index,scene in enumerate(SCENES):
        if scene['kind'] in ('hero','obs','end'):continue
        w=ui.MainWindow(OUT/f'state-{index}')
        w.timer.stop();w.notice_timer.stop()
        w.restore({'input':'Your microphone \u00b7 Windows DirectSound','output':'CABLE Input \u00b7 Windows DirectSound',
                   'session_mode':0,'backend':1,'words':'banana\ncat\ndog','delay':1250,
                   'model':str(ROOT/'models/faster-whisper-small.en')})
        kind=scene['kind']
        if kind in ('live','notice','words','unsupported','switch'):w.session_mode.setCurrentIndex(1)
        target=w.routing
        if kind=='record':
            w.last_recording=OUT/'demo-filtered.wav';w.original_recording=OUT/'demo-original.wav';w.lock(False)
            w.status.setText('STOPPED');w.metrics.setText('Full recording processed | 1 blocked word interval replaced')
            w.recording_status.setText('Saved original and filtered audio locally. Ready to compare.')
            target=w.replay_button
        if kind=='notice':
            w.status.setText('FILTERING');w.violation.setText('Blocked word detected: b*** - censorship scheduled. Avoid repeating it.')
            w.violation.show();w.metrics.setText('Detected 1 | Muted 0.0 s | Queue 0 | Headroom 560 ms')
            target=w.violation
        if kind=='words':
            w.words.appendPlainText('coffee');w.message.setText('Settings validated and saved. The next session will use this word list.')
            target=w.censor_group
        if kind=='unsupported':
            w.words.appendPlainText('unsupported-example')
            w.show_error(UnsupportedWordsError(['unsupported-example']))
            w.status.setText('ERROR - OUTPUT STOPPED');target=w.censor_group
        if kind=='switch':w.session_mode.setCurrentIndex(0)
        w.show();app.processEvents()
        w.grab().save(str(OUT/f'ui-{index}.png'))
        point=target.mapTo(w,QPoint(0,0))
        scene['target']=[point.x(),point.y(),target.width(),target.height()]
        scene['size']=[w.width(),w.height()]
        w.close()
    (OUT/'scenes.json').write_text(json.dumps(SCENES,indent=2),encoding='utf-8')
    print('Offscreen tutorial screenshots prepared.')


W,H,FPS=1920,1080,24
FONT='C:/Windows/Fonts/segoeui.ttf'
BOLD='C:/Windows/Fonts/segoeuib.ttf'
def font(size,bold=False):return ImageFont.truetype(BOLD if bold else FONT,size)
def lines(draw,text,xy,size=30,color='#bbc9dc',width=560,bold=False,spacing=1.3):
    f=font(size,bold);x,y=xy
    for paragraph in text.split('\n'):
        words=paragraph.split();line=''
        for word in words:
            candidate=(line+' '+word).strip()
            if f.getlength(candidate)>width and line:
                draw.text((x,y),line,font=f,fill=color);y+=int(size*spacing);line=word
            else:line=candidate
        if line:draw.text((x,y),line,font=f,fill=color);y+=int(size*spacing)
    return y

def background():
    yy,xx=np.mgrid[0:H,0:W]
    glow=np.exp(-((xx-1520)**2+(yy-170)**2)/(650**2))
    a=np.zeros((H,W,3),dtype=np.uint8)
    for k,(base,gain) in enumerate([(9,9),(17,27),(30,36)]):a[:,:,k]=base+glow*gain
    im=Image.fromarray(a);d=ImageDraw.Draw(im)
    for x in range(0,W,80):d.line((x,0,x,H),fill='#142331',width=1)
    for y in range(0,H,80):d.line((0,y,W,y),fill='#142331',width=1)
    d.rounded_rectangle((68,54,109,95),radius=12,fill='#39d7b2')
    d.line((79,75,87,83,100,65),fill='#0b2430',width=5)
    d.text((123,49),'STREAMGUARD',font=font(33,True),fill='#f4f8ff')
    d.text((1512,58),'QUICK START / 0.3 RC1',font=font(23),fill='#91a6bf')
    return im


def build_scene(scene,index):
    im=background();d=ImageDraw.Draw(im)
    d.text((75,171),scene['label'],font=font(23,True),fill='#46debf')
    end=lines(d,scene['title'],(70,232),size=68,color='#f3f7ff',width=635,bold=True,spacing=1.1)
    lines(d,scene['tip'],(75,end+45),size=32,width=540,color='#bccbdd')
    d.text((75,838),f'{index+1:02d} / {len(SCENES):02d}',font=font(23),fill='#6c849d')
    kind=scene['kind']
    if kind in ('hero','end'):
        cards=([('01','Record & compare','Keep the entire session.'),('02','Filter live','Short, deliberate audience delay.'),('03','Edit with confidence','Validate words. Restart cleanly.')]
               if kind=='hero' else [('01','Full recording','Original + filtered comparison'),('02','Live test','Watch notices and output status'),('03','Local OBS check','Verify routing and A/V sync')])
        for j,(number,title,body) in enumerate(cards):
            y=228+j*190
            d.rounded_rectangle((760,y,1828,y+151),radius=24,fill='#142638',outline='#30485d',width=2)
            d.text((798,y+38),number,font=font(42,True),fill='#45ddbc')
            d.text((890,y+29),title,font=font(36,True),fill='#eff5ff')
            d.text((892,y+83),body,font=font(27),fill='#afc2d7')
    elif kind=='obs':
        for j,(title,desc) in enumerate([('MICROPHONE','Your physical microphone'),('STREAMGUARD','Filter + audience buffer'),('CABLE INPUT / OUTPUT','Virtual audio route'),('OBS','Capture filtered audio only')]):
            y=185+j*164
            d.rounded_rectangle((820,y,1780,y+123),radius=20,fill='#142638',outline='#3b6e72',width=2)
            d.text((860,y+20),title,font=font(31,True),fill='#4de0c1')
            d.text((860,y+65),desc,font=font(27),fill='#d2deed')
            if j<3:d.polygon([(1286,y+132),(1314,y+132),(1300,y+153)],fill='#45ddbc')
    else:
        shot=Image.open(OUT/f'ui-{index}.png').convert('RGB')
        x,y,w,h=scene['target']
        if kind in ('modes','live','switch','words','unsupported'):
            crop=(max(0,x-12),max(0,y-12),min(shot.width,x+w+12),min(shot.height,y+h+12))
        elif kind=='record':crop=(12,max(0,y-70),shot.width-12,min(shot.height,y+210))
        else:crop=(12,90,shot.width-12,min(shot.height,y+h+35))
        shot=shot.crop(crop)
        ratio=min(1070/shot.width,690/shot.height,2.0)
        shot=shot.resize((round(shot.width*ratio),round(shot.height*ratio)),Image.Resampling.LANCZOS)
        sx=750+(1080-shot.width)//2;sy=235+(660-shot.height)//2
        d.rounded_rectangle((sx-15,sy-54,sx+shot.width+15,sy+shot.height+17),radius=22,fill='#182e42',outline='#3c6072',width=2)
        d.text((sx+10,sy-43),'ACTUAL INTERFACE  /  DEMONSTRATION DATA',font=font(18,True),fill='#86b9bd')
        im.paste(shot,(sx,sy))
    return im


def srt_time(seconds):
    ms=round(seconds*1000);h,ms=divmod(ms,3600000);m,ms=divmod(ms,60000);s,ms=divmod(ms,1000)
    return f'{h:02}:{m:02}:{s:02},{ms:03}'


def render():
    import av
    scenes=json.loads((OUT/'scenes.json').read_text(encoding='utf-8'))
    audio_parts=[];durations=[];starts=[];bases=[];elapsed=0;subtitles=[];rate=24000
    for index,scene in enumerate(scenes):
        with wave.open(str(OUT/f'voice-{index}.wav'),'rb') as src:
            assert src.getframerate()==rate and src.getnchannels()==1 and src.getsampwidth()==2
            audio=np.frombuffer(src.readframes(src.getnframes()),dtype='<i2').astype(np.float32)/32768
        duration=math.ceil((len(audio)/rate+1.4)*FPS)/FPS
        starts.append(elapsed);durations.append(duration);elapsed+=duration
        audio_parts.append(np.concatenate([np.zeros(int(.35*rate),np.float32),audio,
            np.zeros(round(duration*rate)-len(audio)-int(.35*rate),np.float32)]))
        bases.append(build_scene(scene,index))
        sentences=[p.strip()+'.' for p in scene['narration'].split('.') if p.strip()]
        total=sum(len(s) for s in sentences);position=starts[-1]+.35
        for sentence in sentences:
            end=position+len(audio)/rate*len(sentence)/total
            subtitles.append((position,end,sentence));position=end
    soundtrack=np.concatenate(audio_parts)
    output=OUT/'StreamGuard-Tutorial.mp4'
    container=av.open(str(output),'w',options={'movflags':'+faststart'})
    video=container.add_stream('libx264',rate=FPS);video.width=W;video.height=H;video.pix_fmt='yuv420p'
    video.options={'crf':'21','preset':'veryfast'};video.codec_context.thread_count=2
    sound=container.add_stream('aac',rate=rate);sound.layout='mono';sound.bit_rate=96000
    frames=round(elapsed*FPS);audio_at=0;scene_index=0;caption_index=0
    for n in range(frames):
        t=n/FPS
        while scene_index+1<len(starts) and t>=starts[scene_index+1]:scene_index+=1
        frame=bases[scene_index].copy();local=t-starts[scene_index]
        if scene_index and local<.35:frame=Image.blend(bases[scene_index-1],frame,local/.35)
        d=ImageDraw.Draw(frame)
        d.rounded_rectangle((68,948,1852,1031),radius=18,fill='#070f1b')
        while caption_index+1<len(subtitles) and t>=subtitles[caption_index][1]:caption_index+=1
        a,b,caption=subtitles[caption_index]
        if a<=t<b:lines(d,caption,(95,962),size=27,color='#e6edf7',width=1720,spacing=1.12)
        d.rounded_rectangle((70,1050,1850,1056),radius=3,fill='#243549')
        d.rounded_rectangle((70,1050,70+max(3,1780*(t/elapsed)),1056),radius=3,fill='#39d7b2')
        vf=av.VideoFrame.from_image(frame);vf.pts=n;vf.time_base=Fraction(1,FPS)
        for packet in video.encode(vf):container.mux(packet)
        target=min(len(soundtrack),round((n+1)*rate/FPS))
        while audio_at+1024<=target:
            af=av.AudioFrame.from_ndarray(soundtrack[audio_at:audio_at+1024].reshape(1,-1),format='fltp',layout='mono')
            af.sample_rate=rate;af.pts=audio_at;af.time_base=Fraction(1,rate)
            for packet in sound.encode(af):container.mux(packet)
            audio_at+=1024
        if n%240==0:print(f'Rendering {n}/{frames} frames',flush=True)
    if audio_at<len(soundtrack):
        af=av.AudioFrame.from_ndarray(soundtrack[audio_at:].reshape(1,-1),format='fltp',layout='mono')
        af.sample_rate=rate;af.pts=audio_at;af.time_base=Fraction(1,rate)
        for packet in sound.encode(af):container.mux(packet)
    for packet in video.encode():container.mux(packet)
    for packet in sound.encode():container.mux(packet)
    container.close()
    (OUT/'StreamGuard-Tutorial.srt').write_text('\n\n'.join(f'{i+1}\n{srt_time(a)} --> {srt_time(b)}\n{text}' for i,(a,b,text) in enumerate(subtitles)),encoding='utf-8')
    transcript='# StreamGuard tutorial\n\nNarrated walkthrough of the 0.3 RC1 English interface. Demonstration data only.\n\n'
    for index,scene in enumerate(scenes):
        transcript+=f"## {int(starts[index])//60:02}:{int(starts[index])%60:02} {scene['title'].replace(chr(10),' ')}\n\n{scene['narration']}\n\n"
        bases[index].save(OUT/f'chapter-{index}.jpg',quality=90)
    (OUT/'Tutorial-transcript.md').write_text(transcript,encoding='utf-8')
    print(json.dumps({'video':str(output),'seconds':elapsed,'frames':frames,'size':output.stat().st_size}),flush=True)


if __name__=='__main__':
    parser=argparse.ArgumentParser();parser.add_argument('--assets',action='store_true');parser.add_argument('--render',action='store_true')
    args=parser.parse_args()
    if args.assets:assets()
    if args.render:render()
