import os.path
import time
import glob
import argparse
import threading
import mido
import numpy as np
import pygame as pg
from moviepy.editor import VideoFileClip

pg.init()
pg.display.set_caption('midi2movie')

def is_midi_change_msg(msg):
    return msg is not None and msg.type == 'note_on'

def is_midi_quit_msg(msg, quitnote):
    return is_midi_change_msg(msg) and msg.note == quitnote

def imdisplay(imarray, screen=None):
    """
    Splashes the given image array on the given pygame screen
    src: https://github.com/Zulko/moviepy/blob/master/moviepy/video/io/preview.py
    """
    a = pg.surfarray.make_surface(imarray.swapaxes(0, 1))
    if screen is None:
        screen = pg.display.set_mode(imarray.shape[:2][::-1])
    screen.blit(a, (0, 0))
    pg.display.flip()

def preview(clip, inport=None, fps=15, audio=True, audio_fps=22050, audio_buffersize=3000, audio_nbytes=2):
    """
    src: https://github.com/Zulko/moviepy/blob/master/moviepy/video/io/preview.py
    """
    import pygame as pg    

    # compute and splash the first image
    screen = pg.display.set_mode(clip.size)
    
    audio = audio and (clip.audio is not None)
    
    if audio:
        # the sound will be played in parrallel. We are not
        # parralellizing it on different CPUs because it seems that
        # pygame and openCV already use several cpus it seems.
        
        # two synchro-flags to tell whether audio and video are ready
        videoFlag = threading.Event()
        audioFlag = threading.Event()
        # launch the thread
        audiothread = threading.Thread(target=clip.audio.preview,
            args = (audio_fps,audio_buffersize, audio_nbytes,
                    audioFlag, videoFlag))
        audiothread.start()
    
    img = clip.get_frame(0)
    imdisplay(img, screen)
    if audio: # synchronize with audio
        videoFlag.set() # say to the audio: video is ready
        audioFlag.wait() # wait for the audio to be ready
    
    result = []
    
    t0 = time.time()
    for t in np.arange(1.0 / fps, clip.duration-.001, 1.0 / fps):
        img = clip.get_frame(t)
        for event in pg.event.get():
            if event.type == pg.KEYDOWN:
                if (event.key == pg.K_ESCAPE):
                    if audio:
                        videoFlag.clear()
                    print( "Keyboard interrupt" )
                    return result
            elif event.type == pg.MOUSEBUTTONDOWN:
                x,y = pg.mouse.get_pos()
                rgb = img[y,x]
                result.append({'time':t, 'position':(x,y),
                                'color':rgb})
                print( "time, position, color : ", "%.03f, %s, %s"%(
                             t,str((x,y)),str(rgb)))
        t1 = time.time()
        time.sleep(max(0, t - (t1-t0)) )
        imdisplay(img, screen)
        if inport is not None:
            msg = inport.poll()
            if is_midi_change_msg(msg):
                return msg

def main(fnms, play_audio=False, loop_until_change=True, port_name=None, quitnote=50):
    """
    plays video clip based on which midi note is played
    """
    clips = [VideoFileClip(fnm) for fnm in fnms]
    clip = None
    msg = None    
    with mido.open_input(port_name) as inport:
        while not is_midi_quit_msg(msg, quitnote):
            if clip is not None: # play current clip
                msg = preview(clip, inport, audio=play_audio)
                if not loop_until_change:
                    clip = None
            else: # check for midi note
                msg = inport.poll()
            if is_midi_change_msg(msg): # update clip
                curInd = msg.note % len(clips)
                clip = clips[curInd]

if __name__ == '__main__':
    ports = mido.get_input_names()
    parser = argparse.ArgumentParser()
    parser.add_argument("--audio", action="store_true", 
        help="play audio along with video")
    parser.add_argument("--loop", action="store_true", 
        help="play most recent video on loop until midi note changes")
    parser.add_argument("--portname", type=str, 
        help="name of midi port (optional)", choices=ports)
    parser.add_argument("--quitnote", type=int,
        default=50, help="which midi note to quit on")
    parser.add_argument("--datadir", type=str,
        default='data',
        help="directory containing videos")
    parser.add_argument("--ext", type=str,
        default='mp4',
        help="video file type to look for")
    args = parser.parse_args()

    if len(ports) == 0:
        print "No midi controllers found."
    else:
        print "Play a note on a midi controller to get started!"
        print "(To quit, play midi note {})".format(args.quitnote)
        fnms = glob.glob(os.path.join(args.datadir, '*.' + args.ext))
        main(fnms, play_audio=args.audio, loop_until_change=args.loop, port_name=args.portname, quitnote=args.quitnote)
